"""天气预警接口：按场区聚合天气与鹅病风险。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session as OrmSession

from core.weather import get_weather
from core.weather_risk import assess, generate_advice
from db.models import TraceBatch
from db.session import get_db

router = APIRouter()


def _farm_rows(db: OrmSession) -> list[dict]:
    """从批次表聚合场区：场名、批次数、在养存栏。"""
    rows = db.execute(
        select(
            TraceBatch.farm_name,
            func.count(TraceBatch.id),
            func.sum(
                case(
                    (TraceBatch.status.in_(("raising", "growing")), TraceBatch.current_quantity),
                    else_=0,
                )
            ),
        ).group_by(TraceBatch.farm_name)
    ).all()
    return [
        {"farm_name": name, "batch_count": count, "alive_quantity": int(alive or 0)}
        for name, count, alive in rows
    ]


@router.get("/weather/farms")
def weather_farms(db: OrmSession = Depends(get_db)):
    """各场区今日天气与未来 3 天风险概览（页面列表用）。"""
    farms = []
    for row in _farm_rows(db):
        weather = get_weather(row["farm_name"])
        result = assess(weather)
        farms.append(
            {
                **row,
                "city": weather["city"],
                "source": weather["source"],
                "demo": weather["demo"],
                "updated_at": weather["updated_at"],
                "current": weather["current"],
                "level": result["level"],
                "label": result["label"],
                "summary": result["summary"],
                "diseases": result["diseases"][:5],
                "days": [
                    {
                        "date": day["date"],
                        "week": day["week"],
                        "text": day["text"],
                        "temp_max": day["temp_max"],
                        "temp_min": day["temp_min"],
                        "level": day["level"],
                        "label": day["label"],
                    }
                    for day in result["days"][:3]
                ],
            }
        )
    farms.sort(key=lambda item: {"high": 0, "medium": 1, "low": 2}[item["level"]])
    return farms


@router.get("/weather/detail")
def weather_detail(farm_name: str = Query(..., description="养殖场名称，如 饶平柘林湾鹅场"), db: OrmSession = Depends(get_db)):
    """单场区 7 天天气、逐日风险命中与防控建议。"""
    known = {row["farm_name"] for row in _farm_rows(db)}
    if known and farm_name not in known:
        raise HTTPException(status_code=404, detail="未找到该养殖场")

    weather = get_weather(farm_name)
    result = assess(weather)
    return {
        "farm_name": farm_name,
        "city": weather["city"],
        "source": weather["source"],
        "demo": weather["demo"],
        "updated_at": weather["updated_at"],
        "current": weather["current"],
        "level": result["level"],
        "label": result["label"],
        "summary": result["summary"],
        "diseases": result["diseases"],
        "advice": generate_advice(weather, result),
        "days": result["days"],
    }
