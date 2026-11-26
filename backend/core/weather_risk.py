"""天气风险规则引擎：把温湿度 / 降雨 / 温差 / 风力映射到鹅病风险。

设计原则：规则可解释、可复现（每条命中都有依据），LLM 只负责把规则结果写成
通顺的防控建议；LLM 不可用时回退到规则内置文案。
"""
from __future__ import annotations

import time
from typing import Any

from core.config import settings

_LEVEL_LABEL = {"high": "高风险", "medium": "中风险", "low": "低风险"}
_LEVEL_WEIGHT = {"high": 3, "medium": 2, "low": 1}

_advice_cache: dict[str, tuple[float, str]] = {}


def _hit(key: str, title: str, level: str, diseases: list[str], advice: str) -> dict[str, Any]:
    return {"key": key, "title": title, "level": level, "diseases": diseases, "advice": advice}


def _day_hits(day: dict[str, Any]) -> list[dict[str, Any]]:
    """对单日天气执行全部规则，返回命中的风险项。"""
    tmax = day.get("temp_max")
    tmin = day.get("temp_min")
    humidity = day.get("humidity")
    precip = day.get("precip")
    wind = day.get("wind_scale") or 1
    text = day.get("text") or ""
    rainy = any(word in text for word in ("雨", "雪", "雷"))
    heavy_rain = any(word in text for word in ("大雨", "暴雨", "强阵雨", "雷"))
    hits: list[dict[str, Any]] = []

    if tmin is not None and tmin <= 8:
        hits.append(
            _hit(
                "cold_wave", "寒潮低温", "high",
                ["雏鹅感冒", "呼吸道疾病", "大肠杆菌病", "沙门氏菌病"],
                "夜间加厚垫料并封好贼风，雏鹅舍温不低于 28℃，饮温水、适当增加能量饲料",
            )
        )
    elif tmin is not None and tmin <= 12:
        hits.append(
            _hit(
                "cold", "气温偏低", "medium",
                ["感冒", "呼吸道疾病"],
                "早晚关窗保温，避免冷风直吹，注意观察扎堆与流涕现象",
            )
        )

    if tmax is not None and tmax >= 35:
        hits.append(
            _hit(
                "heat_wave", "持续高温", "high",
                ["热应激", "中暑", "禽霍乱", "球虫病"],
                "中午喷淋降温、保证清凉饮水，适当降低饲养密度并加强通风",
            )
        )
    elif tmax is not None and tmax >= 32:
        hits.append(
            _hit(
                "heat", "气温偏高", "medium",
                ["热应激", "采食量下降"],
                "加强通风与饮水供应，避开正午高温时段投喂",
            )
        )

    if heavy_rain:
        hits.append(
            _hit(
                "heavy_rain", "强降雨", "high",
                ["球虫病", "曲霉菌病", "鸭疫里默氏菌病", "饲料霉变"],
                "及时排水防积水，垫料勤换保持干燥，饲料防潮并检查霉变",
            )
        )
    elif rainy:
        hits.append(
            _hit(
                "rain", "降雨高湿", "medium",
                ["球虫病", "曲霉菌病", "浆膜炎"],
                "保持舍内干燥、勤换潮湿垫料，雨后加强消毒与粪便清理",
            )
        )

    if humidity is not None and humidity >= 85:
        hits.append(
            _hit(
                "humid", "空气高湿", "medium",
                ["球虫病", "曲霉菌病", "大肠杆菌病"],
                "加强通风除湿，饮水器防漏水，避免垫料板结",
            )
        )
    elif humidity is not None and humidity <= 40:
        hits.append(
            _hit(
                "dry", "空气干燥", "medium",
                ["呼吸道黏膜损伤", "粉尘刺激"],
                "适当喷雾增湿，减少扬尘，保证充足饮水",
            )
        )

    if tmax is not None and tmin is not None and tmax - tmin >= 10:
        hits.append(
            _hit(
                "temp_gap", "昼夜温差大", "medium",
                ["呼吸道疾病", "支原体感染"],
                "夜间注意保温，避免昼夜温差超过 8℃，减少应激",
            )
        )

    if wind >= 5:
        hits.append(
            _hit(
                "wind", "大风天气", "medium",
                ["应激", "呼吸道疾病"],
                "检查棚舍与卷帘固定，防止穿堂风直吹鹅群",
            )
        )

    if tmax is not None and tmax >= 30 and (rainy or (humidity is not None and humidity >= 80)):
        hits.append(
            _hit(
                "heat_humid", "高温高湿叠加", "high",
                ["球虫病", "禽霍乱", "热应激", "曲霉菌病"],
                "高温高湿同时出现时优先降温除湿，饮水中可补充电解多维，并加强粪便清理",
            )
        )
    return hits


def _day_level(hits: list[dict[str, Any]]) -> str:
    level = "low"
    for hit in hits:
        if _LEVEL_WEIGHT[hit["level"]] > _LEVEL_WEIGHT[level]:
            level = hit["level"]
    return level


def _unique(items: list[str]) -> list[str]:
    seen: list[str] = []
    for item in items:
        if item and item not in seen:
            seen.append(item)
    return seen


def assess(weather: dict[str, Any]) -> dict[str, Any]:
    """对 7 天天气逐日跑规则，并汇总未来 3 天的综合风险。"""
    days: list[dict[str, Any]] = []
    for day in weather.get("days") or []:
        hits = _day_hits(day)
        level = _day_level(hits)
        days.append(
            {
                **day,
                "hits": hits,
                "level": level,
                "label": _LEVEL_LABEL[level],
                "diseases": _unique([d for hit in hits for d in hit["diseases"]]),
            }
        )

    focus = days[:3]
    level = "low"
    for day in focus:
        if _LEVEL_WEIGHT[day["level"]] > _LEVEL_WEIGHT[level]:
            level = day["level"]
    diseases = _unique([d for day in focus for d in day["diseases"]])
    advice_short = _unique([hit["advice"] for day in focus for hit in day["hits"]])[:4]
    titles = _unique([hit["title"] for day in focus for hit in day["hits"]])

    if level == "low":
        summary = f"{weather.get('city', '场区')}未来 3 天天气平稳，按常规巡栏与消毒节奏管理即可。"
    else:
        summary = (
            f"{weather.get('city', '场区')}未来 3 天{'、'.join(titles)}，"
            f"综合{_LEVEL_LABEL[level]}，重点防范{'、'.join(diseases[:4])}。"
        )

    return {
        "level": level,
        "label": _LEVEL_LABEL[level],
        "diseases": diseases,
        "advice_short": advice_short,
        "summary": summary,
        "days": days,
    }


def _rule_advice(result: dict[str, Any]) -> str:
    if not result["advice_short"]:
        return "近期天气平稳，保持日常巡栏、清洁消毒与合理通风即可。"
    return "\n".join(f"{idx}. {item}" for idx, item in enumerate(result["advice_short"], 1))


def generate_advice(weather: dict[str, Any], result: dict[str, Any]) -> str:
    """用 LLM 把规则结果写成 4 条防控建议；失败或无 Key 时回退规则文案。"""
    base = _rule_advice(result)
    if not settings.DEEPSEEK_API_KEY or result["level"] == "low":
        return base

    signature = f"{weather.get('city')}:{result['days'][0]['date'] if result['days'] else ''}:{result['level']}"
    cached = _advice_cache.get(signature)
    if cached and time.time() - cached[0] < 7200:
        return cached[1]

    forecast = "\n".join(
        f"{d['date']} {d['text']} {d['temp_min']}~{d['temp_max']}℃，{d['label']}"
        + (f"（{'、'.join(d['diseases'][:4])}）" if d["diseases"] else "")
        for d in result["days"][:3]
    )
    prompt = (
        "你是鹅养殖疫病防控顾问。根据下面的天气预报与已判定的风险，给出 4 条针对性的防控建议。\n"
        f"场区：{weather.get('farm_name') or weather.get('city')}\n{forecast}\n\n"
        "要求：每条一句话、不超过 35 字，按 1. 2. 3. 4. 编号；只输出建议本身，"
        "不要寒暄、不要 Markdown 符号、不要重复天气数据。"
    )
    try:
        from core.llm import get_client

        resp = get_client().chat.completions.create(
            model=settings.DEEPSEEK_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.4,
            max_tokens=220,
        )
        text = (resp.choices[0].message.content or "").strip()
        if text:
            _advice_cache[signature] = (time.time(), text)
            return text
    except Exception:  # noqa: BLE001 —— 回退规则文案
        pass
    return base
