"""会话管理接口：创建 / 列表 / 详情（含消息）/ 删除。"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy import delete, select
from sqlalchemy.orm import Session as OrmSession

from db.models import Message, Session
from db.session import get_db

router = APIRouter()


class SessionCreate(BaseModel):
    title: str | None = None


class SessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    created_at: datetime


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    role: str
    content: str
    sources: str
    created_at: datetime


class SessionDetail(SessionOut):
    messages: list[MessageOut] = []


def _get_session_or_404(db: OrmSession, session_id: int) -> Session:
    session = db.get(Session, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail=f"会话 {session_id} 不存在")
    return session


@router.post("/sessions", response_model=SessionOut)
async def create_session(req: SessionCreate, db: OrmSession = Depends(get_db)):
    """创建会话。"""
    session = Session(title=req.title or "新会话")
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


@router.get("/sessions", response_model=list[SessionOut])
async def list_sessions(db: OrmSession = Depends(get_db)):
    """会话列表（最近更新的在前）。"""
    return db.scalars(select(Session).order_by(Session.updated_at.desc())).all()


@router.get("/sessions/{session_id}", response_model=SessionDetail)
async def get_session(session_id: int, db: OrmSession = Depends(get_db)):
    """会话详情（含全部消息）。"""
    session = _get_session_or_404(db, session_id)
    messages = db.scalars(
        select(Message).where(Message.session_id == session_id).order_by(Message.id)
    ).all()
    return SessionDetail(
        id=session.id, title=session.title, created_at=session.created_at, messages=messages
    )


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: int, db: OrmSession = Depends(get_db)):
    """删除会话（消息级联删除）。"""
    _get_session_or_404(db, session_id)
    db.execute(delete(Message).where(Message.session_id == session_id))
    db.execute(delete(Session).where(Session.id == session_id))
    db.commit()
    return {"deleted": session_id}
