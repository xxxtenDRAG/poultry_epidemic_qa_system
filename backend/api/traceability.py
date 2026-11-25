"""鹅全链路溯源与养殖管理接口。

链路阶段：孵化 → 育雏 → 生长育成 → 防疫与健康 → 出栏检疫 → 屠宰加工 → 质检分级 → 冷链物流 → 终端销售。
养殖管理：批次创建/编辑、日常巡栏记录（死淘、采食、饮水、温湿度、异常与处置）。
"""
import json
from collections import Counter
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session as OrmSession

from core.trace_stages import STAGES, STAGE_MAP, stage_meta
from db.models import FarmDailyRecord, TraceBatch, TraceEvent
from db.session import get_db

router = APIRouter()

VALID_STATUS = {"growing", "ready", "processing", "sold"}
VALID_RISK = {"low", "medium", "high"}


class TraceEventCreate(BaseModel):
    stage: str
    title: str
    event_time: datetime | None = None
    location: str = ""
    operator: str = ""
    detail: dict = Field(default_factory=dict)
    evidence: list[str] = Field(default_factory=list)
    status: str = "done"


class TraceBatchCreate(BaseModel):
    batch_no: str
    farm_name: str
    breed: str = ""
    house_no: str = ""
    hatch_date: datetime
    entry_date: datetime | None = None
    quantity: int = Field(gt=0)
    current_quantity: int | None = Field(default=None, ge=0)
    status: str = "growing"
    current_stage: str = "incubation"
    risk_level: str = "low"


class TraceBatchUpdate(BaseModel):
    farm_name: str | None = None
    breed: str | None = None
    house_no: str | None = None
    hatch_date: datetime | None = None
    entry_date: datetime | None = None
    quantity: int | None = Field(default=None, gt=0)
    current_quantity: int | None = Field(default=None, ge=0)
    status: str | None = None
    current_stage: str | None = None
    risk_level: str | None = None


class DailyRecordCreate(BaseModel):
    record_date: datetime | None = None
    mortality: int = Field(default=0, ge=0)
    culling: int = Field(default=0, ge=0)
    feed_kg: float = Field(default=0, ge=0)
    water_l: float = Field(default=0, ge=0)
    temperature: float | None = None
    humidity: float | None = None
    symptoms: str = ""
    action: str = ""
    note: str = ""
    created_by: str = ""


def _load_json(value: str | None, fallback):
    if not value:
        return fallback
    try:
        parsed = json.loads(value)
    except (TypeError, ValueError):
        return fallback
    return parsed if isinstance(parsed, type(fallback)) else fallback


def _today_start() -> datetime:
    return datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)


def _event_out(event: TraceEvent) -> dict:
    meta = stage_meta(event.stage)
    return {
        "id": event.id,
        "stage": event.stage,
        "stage_name": meta["name"],
        "stage_short": meta["short"],
        "stage_color": meta["color"],
        "title": event.title,
        "event_time": event.event_time,
        "location": event.location,
        "operator": event.operator,
        "detail": _load_json(event.detail, {}),
        "evidence": _load_json(event.evidence, []),
        "status": event.status,
        "sequence": event.sequence,
    }


def _daily_record_out(record: FarmDailyRecord) -> dict:
    return {
        "id": record.id,
        "record_date": record.record_date,
        "age_days": record.age_days,
        "mortality": record.mortality,
        "culling": record.culling,
        "feed_kg": record.feed_kg,
        "water_l": record.water_l,
        "temperature": record.temperature,
        "humidity": record.humidity,
        "symptoms": record.symptoms,
        "action": record.action,
        "note": record.note,
        "created_by": record.created_by,
        "created_at": record.created_at,
    }


def _record_stats_by_batch(db: OrmSession) -> dict[int, dict]:
    rows = db.execute(
        select(
            FarmDailyRecord.batch_id,
            func.count(FarmDailyRecord.id),
            func.max(FarmDailyRecord.record_date),
            func.sum(FarmDailyRecord.mortality),
            func.sum(FarmDailyRecord.culling),
        ).group_by(FarmDailyRecord.batch_id)
    ).all()
    return {
        batch_id: {
            "count": int(count or 0),
            "last_record_date": last_date,
            "mortality_total": int(mortality or 0),
            "culling_total": int(culling or 0),
        }
        for batch_id, count, last_date, mortality, culling in rows
    }


def _today_recorded_batch_ids(db: OrmSession) -> set[int]:
    rows = db.scalars(
        select(FarmDailyRecord.batch_id)
        .where(FarmDailyRecord.record_date >= _today_start())
        .distinct()
    ).all()
    return set(rows)


def _batch_summary(
    batch: TraceBatch,
    events: list[TraceEvent],
    record_stats: dict | None = None,
    today_recorded: bool = False,
) -> dict:
    counts = Counter(event.stage for event in events)
    last_times: dict[str, datetime] = {}
    for event in events:
        if event.event_time and (
            event.stage not in last_times or event.event_time > last_times[event.stage]
        ):
            last_times[event.stage] = event.event_time

    stages = []
    for stage in STAGES:
        key = stage["key"]
        if counts.get(key):
            status = "done"
        elif key == batch.current_stage:
            status = "current"
        else:
            status = "pending"
        stages.append(
            {
                **stage,
                "status": status,
                "event_count": counts.get(key, 0),
                "last_time": last_times.get(key),
            }
        )

    done_count = sum(1 for stage in stages if stage["status"] == "done")
    completeness = round(done_count / len(STAGES) * 100)
    alerts = []
    if batch.risk_level in ("medium", "high"):
        alerts.append(
            {
                "level": batch.risk_level,
                "text": "该批次存在健康风险记录，请关注隔离、用药与检疫证明",
            }
        )
    if completeness < 50 and batch.status != "sold":
        alerts.append(
            {
                "level": "info",
                "text": "追溯链路记录偏少，建议补充孵化、防疫或出栏环节",
            }
        )

    stats = record_stats or {}
    current = stage_meta(batch.current_stage)
    last_event_time = max((event.event_time for event in events if event.event_time), default=None)
    return {
        "id": batch.id,
        "batch_no": batch.batch_no,
        "farm_name": batch.farm_name,
        "breed": batch.breed,
        "house_no": batch.house_no,
        "hatch_date": batch.hatch_date,
        "entry_date": batch.entry_date,
        "quantity": batch.quantity,
        "current_quantity": batch.current_quantity,
        "status": batch.status,
        "current_stage": batch.current_stage,
        "current_stage_name": current["name"],
        "risk_level": batch.risk_level,
        "age_days": max(0, (datetime.now() - batch.hatch_date).days),
        "completeness": completeness,
        "stages": stages,
        "trace_code": f"TRACE-{batch.batch_no}",
        "last_event_time": last_event_time,
        "alerts": alerts,
        "daily_record_count": int(stats.get("count", 0)),
        "last_record_date": stats.get("last_record_date"),
        "mortality_total": int(stats.get("mortality_total", 0)),
        "culling_total": int(stats.get("culling_total", 0)),
        "today_recorded": bool(today_recorded),
    }


def _events_by_batch(db: OrmSession) -> dict[int, list[TraceEvent]]:
    grouped: dict[int, list[TraceEvent]] = {}
    events = db.scalars(
        select(TraceEvent).order_by(TraceEvent.batch_id, TraceEvent.sequence, TraceEvent.id)
    ).all()
    for event in events:
        grouped.setdefault(event.batch_id, []).append(event)
    return grouped


def _status_for_stage(stage: str) -> str:
    if stage == "sales":
        return "sold"
    if stage in ("slaughter", "quality", "coldchain"):
        return "processing"
    if stage == "outbound":
        return "ready"
    return "growing"


def _get_batch_or_404(db: OrmSession, batch_no: str) -> TraceBatch:
    batch = db.scalar(select(TraceBatch).where(TraceBatch.batch_no == batch_no))
    if batch is None:
        raise HTTPException(status_code=404, detail=f"批次 {batch_no} 不存在")
    return batch


@router.get("/traceability/stages")
async def list_stages():
    """链路阶段字典（前端选择器与图例使用）。"""
    return STAGES


@router.get("/traceability/overview")
async def trace_overview(db: OrmSession = Depends(get_db)):
    """溯源/养殖概览：批次、存栏、销售、今日记录与平均链路完整度。"""
    batches = db.scalars(select(TraceBatch)).all()
    events_map = _events_by_batch(db)
    stats_map = _record_stats_by_batch(db)
    today_ids = _today_recorded_batch_ids(db)
    summaries = [
        _batch_summary(batch, events_map.get(batch.id, []), stats_map.get(batch.id), batch.id in today_ids)
        for batch in batches
    ]
    raising = [batch for batch in batches if batch.status in ("growing", "ready")]
    avg = round(sum(item["completeness"] for item in summaries) / len(summaries)) if summaries else 0
    today_mortality = db.scalar(
        select(func.coalesce(func.sum(FarmDailyRecord.mortality), 0)).where(
            FarmDailyRecord.record_date >= _today_start()
        )
    ) or 0
    last_record_at = max(
        (stats.get("last_record_date") for stats in stats_map.values() if stats.get("last_record_date")),
        default=None,
    )
    return {
        "batch_count": len(batches),
        "raising_count": len(raising),
        "processing_count": sum(1 for batch in batches if batch.status == "processing"),
        "sold_count": sum(1 for batch in batches if batch.status == "sold"),
        "total_quantity": sum(batch.quantity for batch in batches),
        "alive_quantity": sum(batch.current_quantity for batch in batches),
        "alert_count": sum(1 for batch in batches if batch.risk_level != "low"),
        "avg_completeness": avg,
        "daily_record_count": sum(stats.get("count", 0) for stats in stats_map.values()),
        "today_recorded_count": sum(1 for batch in raising if batch.id in today_ids),
        "today_missing_count": sum(1 for batch in raising if batch.id not in today_ids),
        "today_mortality": int(today_mortality),
        "last_record_at": last_record_at,
    }


@router.post("/traceability/batches")
async def create_batch(req: TraceBatchCreate, db: OrmSession = Depends(get_db)):
    """新建养殖批次（养殖场建档入口）。"""
    batch_no = req.batch_no.strip()
    farm_name = req.farm_name.strip()
    if not batch_no:
        raise HTTPException(status_code=400, detail="批次号不能为空")
    if not farm_name:
        raise HTTPException(status_code=400, detail="养殖场名称不能为空")
    if req.current_stage not in STAGE_MAP:
        raise HTTPException(status_code=400, detail=f"未知环节：{req.current_stage}")
    if req.status not in VALID_STATUS:
        raise HTTPException(status_code=400, detail=f"未知批次状态：{req.status}")
    if req.risk_level not in VALID_RISK:
        raise HTTPException(status_code=400, detail=f"未知风险等级：{req.risk_level}")
    if db.scalar(select(TraceBatch).where(TraceBatch.batch_no == batch_no)):
        raise HTTPException(status_code=409, detail=f"批次号 {batch_no} 已存在")

    batch = TraceBatch(
        batch_no=batch_no,
        farm_name=farm_name,
        breed=req.breed.strip(),
        house_no=req.house_no.strip(),
        hatch_date=req.hatch_date,
        entry_date=req.entry_date or req.hatch_date,
        quantity=req.quantity,
        current_quantity=req.current_quantity if req.current_quantity is not None else req.quantity,
        status=req.status,
        current_stage=req.current_stage,
        risk_level=req.risk_level,
    )
    db.add(batch)
    db.commit()
    db.refresh(batch)
    return _batch_summary(batch, [])


@router.patch("/traceability/batches/{batch_no}")
async def update_batch(batch_no: str, req: TraceBatchUpdate, db: OrmSession = Depends(get_db)):
    """编辑批次基础信息（场长/技术员用）。"""
    batch = _get_batch_or_404(db, batch_no)
    data = req.model_dump(exclude_unset=True)
    if "current_stage" in data and data["current_stage"] not in STAGE_MAP:
        raise HTTPException(status_code=400, detail=f"未知环节：{data['current_stage']}")
    if "status" in data and data["status"] not in VALID_STATUS:
        raise HTTPException(status_code=400, detail=f"未知批次状态：{data['status']}")
    if "risk_level" in data and data["risk_level"] not in VALID_RISK:
        raise HTTPException(status_code=400, detail=f"未知风险等级：{data['risk_level']}")
    for key, value in data.items():
        if isinstance(value, str):
            value = value.strip()
        setattr(batch, key, value)
    batch.updated_at = datetime.now()
    db.commit()
    db.refresh(batch)
    events = db.scalars(
        select(TraceEvent).where(TraceEvent.batch_id == batch.id).order_by(TraceEvent.sequence)
    ).all()
    stats = _record_stats_by_batch(db).get(batch.id)
    today_ids = _today_recorded_batch_ids(db)
    return _batch_summary(batch, list(events), stats, batch.id in today_ids)


@router.get("/traceability/batches")
async def list_batches(db: OrmSession = Depends(get_db)):
    """批次列表（含当前阶段、风险、今日是否已记录、链路完整度）。"""
    batches = db.scalars(select(TraceBatch).order_by(TraceBatch.updated_at.desc(), TraceBatch.id.desc())).all()
    events_map = _events_by_batch(db)
    stats_map = _record_stats_by_batch(db)
    today_ids = _today_recorded_batch_ids(db)
    return [
        _batch_summary(batch, events_map.get(batch.id, []), stats_map.get(batch.id), batch.id in today_ids)
        for batch in batches
    ]


@router.get("/traceability/batches/{batch_no}")
async def batch_detail(batch_no: str, db: OrmSession = Depends(get_db)):
    """批次详情：基础信息 + 九环节状态 + 追溯事件 + 最近日常记录。"""
    batch = _get_batch_or_404(db, batch_no)
    events = db.scalars(
        select(TraceEvent)
        .where(TraceEvent.batch_id == batch.id)
        .order_by(TraceEvent.sequence, TraceEvent.id)
    ).all()
    records = db.scalars(
        select(FarmDailyRecord)
        .where(FarmDailyRecord.batch_id == batch.id)
        .order_by(FarmDailyRecord.record_date.desc(), FarmDailyRecord.id.desc())
        .limit(30)
    ).all()
    stats = _record_stats_by_batch(db).get(batch.id)
    today_ids = _today_recorded_batch_ids(db)
    return {
        "batch": _batch_summary(batch, list(events), stats, batch.id in today_ids),
        "events": [_event_out(event) for event in events],
        "daily_records": [_daily_record_out(record) for record in records],
    }


@router.post("/traceability/batches/{batch_no}/events")
async def create_event(
    batch_no: str,
    req: TraceEventCreate,
    db: OrmSession = Depends(get_db),
):
    """登记一条追溯事件，并同步批次当前环节/状态。"""
    if req.stage not in STAGE_MAP:
        raise HTTPException(status_code=400, detail=f"未知环节：{req.stage}")
    title = (req.title or "").strip()
    if not title:
        raise HTTPException(status_code=400, detail="事件标题不能为空")

    batch = _get_batch_or_404(db, batch_no)
    max_seq = db.scalar(
        select(func.max(TraceEvent.sequence)).where(TraceEvent.batch_id == batch.id)
    ) or 0
    event = TraceEvent(
        batch_id=batch.id,
        stage=req.stage,
        title=title,
        event_time=req.event_time or datetime.now(),
        location=(req.location or "").strip(),
        operator=(req.operator or "").strip(),
        detail=json.dumps(req.detail or {}, ensure_ascii=False),
        evidence=json.dumps(req.evidence or [], ensure_ascii=False),
        status=req.status or "done",
        sequence=max_seq + 1,
    )
    db.add(event)
    batch.current_stage = req.stage
    batch.status = _status_for_stage(req.stage)
    batch.updated_at = datetime.now()
    db.commit()
    db.refresh(event)
    return _event_out(event)


@router.get("/traceability/batches/{batch_no}/daily-records")
async def list_daily_records(
    batch_no: str,
    limit: int = Query(30, ge=1, le=100, description="返回条数上限"),
    db: OrmSession = Depends(get_db),
):
    """批次日常巡栏记录（最新在前）。"""
    batch = _get_batch_or_404(db, batch_no)
    records = db.scalars(
        select(FarmDailyRecord)
        .where(FarmDailyRecord.batch_id == batch.id)
        .order_by(FarmDailyRecord.record_date.desc(), FarmDailyRecord.id.desc())
        .limit(limit)
    ).all()
    return [_daily_record_out(record) for record in records]


@router.post("/traceability/batches/{batch_no}/daily-records")
async def create_daily_record(
    batch_no: str,
    req: DailyRecordCreate,
    db: OrmSession = Depends(get_db),
):
    """记一笔日常巡栏：死淘会同步扣减批次存栏。"""
    batch = _get_batch_or_404(db, batch_no)
    record_date = req.record_date or datetime.now()
    record = FarmDailyRecord(
        batch_id=batch.id,
        record_date=record_date,
        age_days=max(0, (record_date - batch.hatch_date).days),
        mortality=req.mortality,
        culling=req.culling,
        feed_kg=req.feed_kg,
        water_l=req.water_l,
        temperature=req.temperature,
        humidity=req.humidity,
        symptoms=(req.symptoms or "").strip(),
        action=(req.action or "").strip(),
        note=(req.note or "").strip(),
        created_by=(req.created_by or "").strip(),
    )
    db.add(record)
    batch.current_quantity = max(0, batch.current_quantity - req.mortality - req.culling)
    batch.updated_at = datetime.now()
    db.commit()
    db.refresh(record)
    return _daily_record_out(record)
