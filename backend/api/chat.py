"""对话接口：POST /api/chat/stream（SSE 流式，真实流式生成）。

流程：保存用户消息 → 检索（线程池）→ DeepSeek 流式生成（线程池，token 过
队列回传事件循环）→ 逐 token 推送 → 保存助手消息（含溯源）→ done 事件。
DeepSeek 首 token 到达即推送，无需等完整答案。
"""
import asyncio
import json
from typing import AsyncGenerator

import anyio
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session as OrmSession

from agent.graph import finish, prepare, stream_generate
from db.models import Message, Session
from db.session import get_db

router = APIRouter()

_DONE = object()  # 生产者结束哨兵


class ChatRequest(BaseModel):
    session_id: int | None = None
    question: str


async def _stream_answer(question: str, session_id: int, db: OrmSession) -> AsyncGenerator[str, None]:
    # 保存用户消息
    db.add(Message(session_id=session_id, role="user", content=question))
    db.commit()

    # 阶段一：理解 + 检索（同步阻塞，放线程池）
    try:
        state = await anyio.to_thread.run_sync(prepare, question)
    except Exception as e:
        db.rollback()
        yield f"data: {json.dumps({'type': 'error', 'message': f'检索失败：{e}'}, ensure_ascii=False)}\n\n"
        return

    # 阶段二：DeepSeek 流式生成。LLM 阻塞在生产者线程，token 经队列传回事件循环。
    queue: asyncio.Queue = asyncio.Queue()
    error_holder: dict = {}

    def producer() -> None:
        try:
            for token in stream_generate(state):
                queue.put_nowait(token)
        except Exception as e:  # noqa: BLE001
            error_holder["error"] = e
        finally:
            queue.put_nowait(_DONE)

    loop = asyncio.get_running_loop()
    producer_task = loop.run_in_executor(None, producer)

    while True:
        item = await queue.get()
        if item is _DONE:
            break
        yield f"data: {json.dumps({'type': 'token', 'content': item}, ensure_ascii=False)}\n\n"

    await producer_task  # 确保生产者结束

    if "error" in error_holder:
        db.rollback()
        yield f"data: {json.dumps({'type': 'error', 'message': f'生成失败：{error_holder["error"]}'}, ensure_ascii=False)}\n\n"
        return

    # 阶段三：溯源 + 保存助手消息
    sources = finish(state)
    db.add(
        Message(
            session_id=session_id,
            role="assistant",
            content=state["answer"],
            sources=json.dumps(sources, ensure_ascii=False),
        )
    )
    db.commit()

    yield f"data: {json.dumps({'type': 'done', 'answer': state['answer'], 'sources': sources}, ensure_ascii=False)}\n\n"


@router.post("/chat/stream")
async def chat_stream(req: ChatRequest, db: OrmSession = Depends(get_db)):
    """SSE 流式问答。session_id 为空或不存在时自动创建新会话。"""
    session_id = req.session_id
    if session_id is None or db.get(Session, session_id) is None:
        session = Session(title=req.question[:20])
        db.add(session)
        db.commit()
        db.refresh(session)
        session_id = session.id

    return StreamingResponse(
        _stream_answer(req.question, session_id, db),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
