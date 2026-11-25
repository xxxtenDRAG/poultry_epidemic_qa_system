"""MySQL 数据模型（对应《详细实施方案》ER 设计）。

表：session（会话）、message（对话消息）、document（文档元数据）、
trace_batch（鹅批次）、trace_event（全链路追溯事件）、farm_daily_record（日常养殖记录）。
"""
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.session import Base


class Session(Base):
    __tablename__ = "session"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(255), default="新会话")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class Message(Base):
    __tablename__ = "message"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("session.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(16))  # user / assistant
    content: Mapped[str] = mapped_column(Text)
    sources: Mapped[str] = mapped_column(Text, default="[]")  # 溯源 JSON
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Document(Base):
    __tablename__ = "document"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    filename: Mapped[str] = mapped_column(String(255))
    file_path: Mapped[str] = mapped_column(String(512), default="")
    file_type: Mapped[str] = mapped_column(String(32), default="")
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(32), default="pending")  # pending/processing/done/failed
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class TraceBatch(Base):
    """鹅养殖批次：从孵化到销售的一条完整追溯链。"""

    __tablename__ = "trace_batch"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    batch_no: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    farm_name: Mapped[str] = mapped_column(String(128))
    breed: Mapped[str] = mapped_column(String(64), default="")
    house_no: Mapped[str] = mapped_column(String(64), default="")
    hatch_date: Mapped[datetime] = mapped_column(DateTime)
    entry_date: Mapped[datetime] = mapped_column(DateTime)
    quantity: Mapped[int] = mapped_column(Integer, default=0)
    current_quantity: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(32), default="growing")  # growing/ready/processing/sold
    current_stage: Mapped[str] = mapped_column(String(32), default="incubation")
    risk_level: Mapped[str] = mapped_column(String(16), default="low")  # low/medium/high
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    events: Mapped[list["TraceEvent"]] = relationship(
        back_populates="batch",
        cascade="all, delete-orphan",
        order_by="TraceEvent.sequence",
    )
    daily_records: Mapped[list["FarmDailyRecord"]] = relationship(
        back_populates="batch",
        cascade="all, delete-orphan",
        order_by="FarmDailyRecord.record_date",
    )


class TraceEvent(Base):
    """批次在某个环节发生的一条可追溯记录。"""

    __tablename__ = "trace_event"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    batch_id: Mapped[int] = mapped_column(
        ForeignKey("trace_batch.id", ondelete="CASCADE"), index=True
    )
    stage: Mapped[str] = mapped_column(String(32))  # 见 core.trace_stages.STAGES
    title: Mapped[str] = mapped_column(String(128))
    event_time: Mapped[datetime] = mapped_column(DateTime)
    location: Mapped[str] = mapped_column(String(128), default="")
    operator: Mapped[str] = mapped_column(String(64), default="")
    detail: Mapped[str] = mapped_column(Text, default="{}")      # JSON：关键指标/说明
    evidence: Mapped[str] = mapped_column(Text, default="[]")    # JSON：佐证材料清单
    status: Mapped[str] = mapped_column(String(16), default="done")
    sequence: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    batch: Mapped["TraceBatch"] = relationship(back_populates="events")


class FarmDailyRecord(Base):
    """养殖场日常巡栏记录：死淘、采食、饮水、温湿度、异常与处置。"""

    __tablename__ = "farm_daily_record"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    batch_id: Mapped[int] = mapped_column(
        ForeignKey("trace_batch.id", ondelete="CASCADE"), index=True
    )
    record_date: Mapped[datetime] = mapped_column(DateTime, index=True)
    age_days: Mapped[int] = mapped_column(Integer, default=0)
    mortality: Mapped[int] = mapped_column(Integer, default=0)
    culling: Mapped[int] = mapped_column(Integer, default=0)
    feed_kg: Mapped[float] = mapped_column(Float, default=0)
    water_l: Mapped[float] = mapped_column(Float, default=0)
    temperature: Mapped[float | None] = mapped_column(Float, nullable=True)
    humidity: Mapped[float | None] = mapped_column(Float, nullable=True)
    symptoms: Mapped[str] = mapped_column(Text, default="")
    action: Mapped[str] = mapped_column(Text, default="")
    note: Mapped[str] = mapped_column(Text, default="")
    created_by: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    batch: Mapped["TraceBatch"] = relationship(back_populates="daily_records")
