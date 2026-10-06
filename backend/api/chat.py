"""对话接口：POST /api/chat/stream（SSE 流式，真实流式生成）。

流程：保存用户消息 → 检索（线程池）→ DeepSeek 流式生成（线程池，token 过
队列回传事件循环）→ 逐 token 推送 → 保存助手消息（含溯源）→ done 事件。
DeepSeek 首 token 到达即推送，无需等完整答案。
"""
import asyncio
import json
import uuid
from pathlib import Path
from typing import AsyncGenerator

import anyio
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session as OrmSession

from agent.graph import finish, prepare, stream_generate
from db.models import Message, Session
from db.session import get_db

router = APIRouter()

UPLOAD_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "uploads"

_DONE = object()  # 生产者结束哨兵


class ChatRequest(BaseModel):
    session_id: int | None = None
    question: str = ""
    image_url: str | None = None  # 用户上传的图片 URL（如 /uploads/xxx.jpg）


@router.post("/chat/upload-image")
async def upload_chat_image(file: UploadFile = File(...)):
    suffix = Path(file.filename or ".jpg").suffix.lower()
    if suffix not in {".jpg", ".jpeg", ".png", ".webp", ".gif"}:
        raise HTTPException(status_code=400, detail="仅支持 jpg/png/webp/gif")
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    uid = uuid.uuid4().hex
    target = UPLOAD_DIR / f"{uid}{suffix}"
    target.write_bytes(await file.read())
    return {"url": f"/uploads/{target.name}"}


async def _stream_answer(question: str, image_url: str | None, session_id: int, db: OrmSession) -> AsyncGenerator[str, None]:
    # 保存用户消息
    db.add(Message(session_id=session_id, role="user", content=question))
    db.commit()

    # 如果带图片，先调用视觉模型识别
    image_desc = ""
    if image_url:
        from agent.graph import identify_disease
        img_path = Path(__file__).resolve().parent.parent.parent / "data" / "uploads" / Path(image_url).name
        if img_path.exists():
            try:
                image_desc = identify_disease(str(img_path))
            except Exception as e:
                image_desc = f"（图片识别失败：{e}）"
        else:
            image_desc = "（图片未找到）"

    # 把图片描述和原问题拼在一起
    if image_desc:
        enriched_question = f"【用户上传了鹅病图片，识别结果如下】\n{image_desc}\n\n用户原问题：{question}"
    else:
        enriched_question = question

    # 急症预警：问题或图片识别结果命中急性疫情信号词时，前端展示红色警示条
    from agent.graph import detect_emergency
    is_emergency = detect_emergency(f"{question}\n{image_desc}")

    # 阶段一：理解 + 检索（同步阻塞，放线程池）
    try:
        state = await anyio.to_thread.run_sync(prepare, enriched_question)
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

    yield f"data: {json.dumps({'type': 'done', 'answer': state['answer'], 'sources': sources, 'alert': is_emergency}, ensure_ascii=False)}\n\n"


@router.post("/chat/stream")
async def chat_stream(req: ChatRequest, db: OrmSession = Depends(get_db)):
    """SSE 流式问答。session_id 为空或不存在时自动创建新会话。"""
    session_id = req.session_id
    if session_id is None or db.get(Session, session_id) is None:
        session = Session(title=req.question[:20] or "图片识别")
        db.add(session)
        db.commit()
        db.refresh(session)
        session_id = session.id

    return StreamingResponse(
        _stream_answer(req.question, req.image_url, session_id, db),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
