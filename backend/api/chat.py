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
from sqlalchemy import select
from sqlalchemy.orm import Session as OrmSession

from agent.graph import finish, prepare, stream_generate
from core.config import settings
from db.models import Message, Session
from db.session import get_db

router = APIRouter()

UPLOAD_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "uploads"

MAX_CHAT_IMAGES = 3  # 单条消息最多携带的图片数，避免视觉模型逐张识别耗时过长

_DONE = object()  # 生产者结束哨兵


class ChatRequest(BaseModel):
    session_id: int | None = None
    question: str = ""
    image_urls: list[str] = []  # 用户上传的图片 URL 列表（如 /uploads/xxx.jpg），最多 MAX_CHAT_IMAGES 张


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


def _load_history(db: OrmSession, session_id: int, current_msg_id: int) -> list[dict]:
    """取当前消息之前最近的若干轮对话（按时间正序返回），供多轮指代消解与生成。

    受 HISTORY_MAX_TURNS（消息条数 = 轮数×2）与 HISTORY_MAX_CHARS 双重约束；
    超字符上限时优先保留最近的消息，空内容（如纯图片提问）自动跳过。
    """
    rows = db.scalars(
        select(Message)
        .where(Message.session_id == session_id, Message.id < current_msg_id)
        .order_by(Message.id.desc())
        .limit(settings.HISTORY_MAX_TURNS * 2)
    ).all()
    history: list[dict] = []
    used = 0
    for row in rows:  # 新 → 旧遍历
        content = (row.content or "").strip()
        if not content:
            continue
        if used + len(content) > settings.HISTORY_MAX_CHARS:
            break  # 更早的消息一并舍弃，保证留下的是最近且完整的上下文
        used += len(content)
        history.append({"role": row.role, "content": content})
    history.reverse()
    return history


async def _stream_answer(question: str, image_urls: list[str], session_id: int, db: OrmSession) -> AsyncGenerator[str, None]:
    # 保存用户消息
    user_msg = Message(session_id=session_id, role="user", content=question)
    db.add(user_msg)
    db.commit()
    db.refresh(user_msg)

    # 加载本会话最近对话，支持追问时指代消解（“它/这个病”）与连贯作答
    history = _load_history(db, session_id, user_msg.id)

    # 如果带图片，逐张调用视觉模型识别（超量部分截断）
    image_descs: list[str] = []
    if image_urls:
        from agent.graph import identify_disease
        for url in image_urls[:MAX_CHAT_IMAGES]:
            img_path = UPLOAD_DIR / Path(url).name
            if not img_path.exists():
                image_descs.append("（图片未找到）")
                continue
            try:
                image_descs.append(identify_disease(str(img_path)))
            except Exception as e:
                image_descs.append(f"（图片识别失败：{e}）")

    # 把各图片识别结果和原问题拼在一起
    if image_descs:
        desc_blocks = [f"【用户上传了 {len(image_descs)} 张鹅病图片，识别结果如下】"]
        desc_blocks += [f"图片{i}：{d}" for i, d in enumerate(image_descs, 1)]
        enriched_question = "\n\n".join(desc_blocks) + f"\n\n用户原问题：{question}"
    else:
        enriched_question = question

    # 急症预警：问题或图片识别结果命中急性疫情信号词时，前端展示红色警示条
    from agent.graph import detect_emergency
    is_emergency = detect_emergency("\n".join([question, *image_descs]))

    # 阶段一：理解 + 检索（同步阻塞，放线程池）
    try:
        state = await anyio.to_thread.run_sync(prepare, enriched_question, history)
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
        _stream_answer(req.question, req.image_urls, session_id, db),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
