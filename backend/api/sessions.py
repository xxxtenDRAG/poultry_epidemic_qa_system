"""会话管理接口：创建 / 列表（可按关键字与提问维度筛选）/ 概览 / 详情 / 删除。

「提问维度」由 core.topics 的关键词规则识别，不落库：会话内容改了就按最新内容重算，
避免新增维度或调整关键词时还要回头刷历史数据。
"""
from collections import Counter
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import delete, select
from sqlalchemy.orm import Session as OrmSession

from core.topics import (
    FALLBACK_QUESTIONS,
    FALLBACK_TOPIC_ID,
    FALLBACK_TOPIC_LABEL,
    SCORE_TEXT_LIMIT,
    TOPICS,
    detect_topics,
)
from db.models import Message, Session
from db.session import get_db

router = APIRouter()

# 会话标题/首问在列表里的展示长度
TITLE_PREVIEW_LIMIT = 80


class SessionCreate(BaseModel):
    title: str | None = None


class SessionOut(BaseModel):
    id: int
    title: str
    created_at: datetime
    last_active_at: datetime | None = None   # 最近一条消息时间（无消息时回落为创建时间）
    message_count: int = 0
    question_count: int = 0
    first_question: str = ""
    topics: list[str] = []                   # 命中的提问维度 id


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    role: str
    content: str
    sources: str
    created_at: datetime


class SessionDetail(SessionOut):
    messages: list[MessageOut] = []


class DimensionOut(BaseModel):
    id: str
    label: str
    count: int                  # 命中该维度的会话数
    questions: list[str] = []   # 该维度的快捷提问模板


class OverviewOut(BaseModel):
    session_count: int
    message_count: int
    question_count: int
    dimension_count: int        # 有会话命中的维度数
    latest_at: datetime | None
    dimensions: list[DimensionOut] = []


class SessionDelete(BaseModel):
    ids: list[int] = []


def _get_session_or_404(db: OrmSession, session_id: int) -> Session:
    session = db.get(Session, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail=f"会话 {session_id} 不存在")
    return session


def _aggregate(db: OrmSession) -> dict[int, dict]:
    """一次查出全部消息并按会话聚合，避免按会话逐条查（N+1）。

    分别累积「全部消息文本」（供关键字搜索）与「用户提问文本」（供维度识别）：
    助手答案动辄上千字，混在一起会把提问维度带偏。
    """
    rows = db.execute(
        select(Message.session_id, Message.role, Message.content, Message.created_at).order_by(
            Message.id
        )
    ).all()

    agg: dict[int, dict] = {}
    for session_id, role, content, created_at in rows:
        item = agg.setdefault(
            session_id,
            {
                "message_count": 0,
                "question_count": 0,
                "last_active_at": None,
                "first_question": "",
                "all_text": [],
                "question_text": [],
                "chars": 0,
                "question_chars": 0,
            },
        )
        item["message_count"] += 1
        text = (content or "").strip()
        if role == "user":
            item["question_count"] += 1
            if not item["first_question"]:
                item["first_question"] = text
            if item["question_chars"] < SCORE_TEXT_LIMIT:
                item["question_text"].append(text)
                item["question_chars"] += len(text)
        if created_at and (item["last_active_at"] is None or created_at > item["last_active_at"]):
            item["last_active_at"] = created_at
        if item["chars"] < SCORE_TEXT_LIMIT:
            item["all_text"].append(text)
            item["chars"] += len(text)
    return agg


def _all_text(agg: dict[int, dict], session_id: int) -> str:
    """会话的全部消息文本（关键字搜索用）。"""
    return "\n".join((agg.get(session_id) or {}).get("all_text") or [])


def _to_out(session: Session, agg: dict[int, dict]) -> SessionOut:
    """把会话行 + 聚合结果拼成列表项（含维度标签）。"""
    item = agg.get(session.id) or {}
    question_text = "\n".join(item.get("question_text") or [])
    return SessionOut(
        id=session.id,
        title=session.title,
        created_at=session.created_at,
        last_active_at=item.get("last_active_at") or session.created_at,
        message_count=item.get("message_count", 0),
        question_count=item.get("question_count", 0),
        first_question=(item.get("first_question") or "")[:TITLE_PREVIEW_LIMIT],
        # 维度按「用户问了什么」判定，标题兜底（自动标题常是首问前 20 字）
        topics=detect_topics(f"{session.title}\n{question_text}"),
    )


@router.post("/sessions", response_model=SessionOut)
async def create_session(req: SessionCreate, db: OrmSession = Depends(get_db)):
    """创建会话。"""
    session = Session(title=req.title or "新会话")
    db.add(session)
    db.commit()
    db.refresh(session)
    return _to_out(session, {})


@router.get("/sessions/overview", response_model=OverviewOut)
async def sessions_overview(db: OrmSession = Depends(get_db)):
    """会话概览：总量统计 + 各提问维度的会话数（历史页概览卡片与维度筛选用）。"""
    sessions = db.scalars(select(Session)).all()
    agg = _aggregate(db)

    topic_counts: Counter = Counter()
    message_total = 0
    question_total = 0
    latest_at: datetime | None = None

    for session in sessions:
        out = _to_out(session, agg)
        message_total += out.message_count
        question_total += out.question_count
        if out.last_active_at and (latest_at is None or out.last_active_at > latest_at):
            latest_at = out.last_active_at
        for topic_id in out.topics:
            topic_counts[topic_id] += 1

    dimensions = [
        DimensionOut(
            id=topic.id,
            label=topic.label,
            count=topic_counts.get(topic.id, 0),
            questions=list(topic.questions),
        )
        for topic in TOPICS
    ]
    dimensions.append(
        DimensionOut(
            id=FALLBACK_TOPIC_ID,
            label=FALLBACK_TOPIC_LABEL,
            count=topic_counts.get(FALLBACK_TOPIC_ID, 0),
            questions=list(FALLBACK_QUESTIONS),
        )
    )

    return OverviewOut(
        session_count=len(sessions),
        message_count=message_total,
        question_count=question_total,
        dimension_count=sum(1 for dim in dimensions if dim.count > 0),
        latest_at=latest_at,
        dimensions=dimensions,
    )


@router.get("/sessions", response_model=list[SessionOut])
async def list_sessions(
    keyword: str = Query("", description="按会话标题或消息内容过滤"),
    topic: str = Query("", description="按提问维度 id 过滤，如 diagnosis"),
    db: OrmSession = Depends(get_db),
):
    """会话列表（最近活动在前）：支持关键字与提问维度筛选。"""
    sessions = db.scalars(select(Session)).all()
    agg = _aggregate(db)
    kw = keyword.strip()

    items: list[SessionOut] = []
    for session in sessions:
        out = _to_out(session, agg)
        if topic and topic not in out.topics:
            continue
        if kw:
            text = _all_text(agg, session.id)
            if kw not in session.title and kw not in text:
                continue
        items.append(out)

    items.sort(key=lambda item: item.last_active_at or item.created_at, reverse=True)
    return items


@router.post("/sessions/delete")
async def delete_sessions(req: SessionDelete, db: OrmSession = Depends(get_db)):
    """批量删除会话（消息一并删除）。"""
    if not req.ids:
        raise HTTPException(status_code=400, detail="没有要删除的会话")
    db.execute(delete(Message).where(Message.session_id.in_(req.ids)))
    db.execute(delete(Session).where(Session.id.in_(req.ids)))
    db.commit()
    return {"deleted": len(req.ids)}


@router.get("/sessions/{session_id}", response_model=SessionDetail)
async def get_session(session_id: int, db: OrmSession = Depends(get_db)):
    """会话详情（含全部消息，按时间正序）。"""
    session = _get_session_or_404(db, session_id)
    messages = db.scalars(
        select(Message).where(Message.session_id == session_id).order_by(Message.id)
    ).all()
    out = _to_out(session, _aggregate(db))
    return SessionDetail(**out.model_dump(), messages=list(messages))


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: int, db: OrmSession = Depends(get_db)):
    """删除会话（消息级联删除）。"""
    _get_session_or_404(db, session_id)
    db.execute(delete(Message).where(Message.session_id == session_id))
    db.execute(delete(Session).where(Session.id == session_id))
    db.commit()
    return {"deleted": session_id}
