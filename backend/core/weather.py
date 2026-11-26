"""天气数据服务：场区定位 → 实时天气与 7 天预报 → 30 分钟内存缓存。

数据源优先级（WEATHER_PROVIDER=auto 时）：
1. Open-Meteo（免 Key，字段最全）—— 本机网络不可达时自动跳过；
2. 中国天气网公开接口（itboy 镜像，免 Key，国内可直连，含 15 天预报）；
3. 内置演示数据（完全离线，用于断网演示）。

统一输出结构：
{
  "farm_name": str, "city": str, "source": "open-meteo|itboy|demo",
  "updated_at": "2026-11-26 12:30", "demo": bool,
  "current": {"temp": 20.3, "humidity": 70, "text": "多云", "wind_scale": 1},
  "days": [{"date": "2026-11-26", "week": "星期四", "text": "小雨",
            "temp_max": 20, "temp_min": 16, "humidity": 70,
            "precip": None, "wind_scale": 1}]
}
"""
from __future__ import annotations

import json
import re
import time
import urllib.parse
import urllib.request
from datetime import datetime
from typing import Any

from core.config import settings

# ---- 场区 → 城市 / 坐标 ----
# 现阶段批次表只有 farm_name，用关键字映射到地级市；新增场区补充到这里即可。
LOCATIONS: list[dict[str, Any]] = [
    {
        "keywords": ("饶平", "柘林"),
        "city": "潮州市",
        "city_key": "101281501",
        "lat": 23.663,
        "lon": 117.005,
    },
    {
        "keywords": ("澄海", "隆都"),
        "city": "汕头市",
        "city_key": "101280501",
        "lat": 23.466,
        "lon": 116.762,
    },
    {
        "keywords": ("梅州", "丙村"),
        "city": "梅州市",
        "city_key": "101280401",
        "lat": 24.273,
        "lon": 116.181,
    },
    {
        "keywords": ("兴宁", "合水"),
        "city": "梅州市",
        "city_key": "101280401",
        "lat": 24.142,
        "lon": 115.731,
    },
]

DEFAULT_LOCATION = LOCATIONS[0]

# 城市名 → 坐标（问诊里用户只说城市名时使用）
CITY_LOCATIONS: dict[str, dict[str, Any]] = {
    "潮州": LOCATIONS[0],
    "汕头": LOCATIONS[1],
    "澄海": LOCATIONS[1],
    "梅州": LOCATIONS[2],
    "兴宁": LOCATIONS[3],
}

_WMO_TEXT = {
    0: "晴", 1: "晴间多云", 2: "多云", 3: "阴", 45: "雾", 48: "雾凇",
    51: "毛毛雨", 53: "毛毛雨", 55: "毛毛雨", 56: "冻雨", 57: "冻雨",
    61: "小雨", 63: "中雨", 65: "大雨", 66: "冻雨", 67: "冻雨",
    71: "小雪", 73: "中雪", 75: "大雪", 77: "雪粒",
    80: "阵雨", 81: "阵雨", 82: "强阵雨", 85: "阵雪", 86: "阵雪",
    95: "雷阵雨", 96: "雷阵雨伴冰雹", 99: "雷阵雨伴冰雹",
}

_cache: dict[str, tuple[float, dict[str, Any]]] = {}


def _http_json(url: str, timeout: float) -> dict[str, Any]:
    req = urllib.request.Request(url, headers={"User-Agent": "goose-weather/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 - 固定可信地址
        return json.loads(resp.read().decode("utf-8", errors="ignore"))


def _wind_scale(kmh: float) -> int:
    """风速 km/h 近似换算蒲福风级（5 级及以上才进入大风规则）。"""
    for limit, scale in ((6, 1), (12, 2), (20, 3), (29, 4), (39, 5), (50, 6)):
        if kmh < limit:
            return scale
    return 7


def _num(value: str | None) -> int | None:
    if not value:
        return None
    match = re.search(r"-?\d+", value)
    return int(match.group()) if match else None


def _fetch_itboy(location: dict[str, Any]) -> dict[str, Any]:
    """中国天气网公开接口（免 Key）。"""
    url = f"http://t.weather.itboy.net/api/weather/city/{location['city_key']}"
    raw = _http_json(url, timeout=8)
    data = raw.get("data") or {}
    forecast = data.get("forecast") or []
    today = forecast[0] if forecast else {}
    humidity = _num(data.get("shidu"))
    days: list[dict[str, Any]] = []
    for idx, item in enumerate(forecast[:7]):
        days.append(
            {
                "date": item.get("ymd") or "",
                "week": item.get("week") or "",
                "text": item.get("type") or "未知",
                "temp_max": _num(item.get("high")),
                "temp_min": _num(item.get("low")),
                "humidity": humidity if idx == 0 else None,
                "precip": None,
                "wind_scale": _num(item.get("fl")) or 1,
            }
        )
    return {
        "farm_name": "",
        "city": (raw.get("cityInfo") or {}).get("city") or location["city"],
        "source": "itboy",
        "updated_at": f"{datetime.now():%Y-%m-%d %H:%M}",
        "demo": False,
        "current": {
            "temp": float(data.get("wendu")) if str(data.get("wendu", "")).replace(".", "").isdigit() else None,
            "humidity": humidity,
            "text": today.get("type") or "",
            "wind_scale": _num(today.get("fl")) or 1,
        },
        "days": days,
    }


def _fetch_open_meteo(location: dict[str, Any]) -> dict[str, Any]:
    """Open-Meteo（免 Key，含降水量，网络可达时优先）。"""
    params = {
        "latitude": location["lat"],
        "longitude": location["lon"],
        "daily": ",".join(
            [
                "temperature_2m_max",
                "temperature_2m_min",
                "precipitation_sum",
                "precipitation_probability_max",
                "wind_speed_10m_max",
                "weather_code",
            ]
        ),
        "current": "temperature_2m,relative_humidity_2m,weather_code",
        "timezone": "Asia/Shanghai",
        "forecast_days": 7,
    }
    url = "https://api.open-meteo.com/v1/forecast?" + urllib.parse.urlencode(params)
    raw = _http_json(url, timeout=float(settings.WEATHER_TIMEOUT))
    daily = raw.get("daily") or {}
    current = raw.get("current") or {}
    dates = daily.get("time") or []
    days: list[dict[str, Any]] = []
    for idx, date in enumerate(dates):
        code = (daily.get("weather_code") or [None] * 7)[idx]
        tmax = (daily.get("temperature_2m_max") or [None] * 7)[idx]
        tmin = (daily.get("temperature_2m_min") or [None] * 7)[idx]
        wind = (daily.get("wind_speed_10m_max") or [None] * 7)[idx]
        days.append(
            {
                "date": date,
                "week": f"周{'一二三四五六日'[datetime.fromisoformat(date).weekday()]}",
                "text": _WMO_TEXT.get(code, "未知") if code is not None else "未知",
                "temp_max": round(tmax) if tmax is not None else None,
                "temp_min": round(tmin) if tmin is not None else None,
                "humidity": current.get("relative_humidity_2m") if idx == 0 else None,
                "precip": (daily.get("precipitation_sum") or [None] * 7)[idx],
                "wind_scale": _wind_scale(wind or 0),
            }
        )
    return {
        "farm_name": "",
        "city": location["city"],
        "source": "open-meteo",
        "updated_at": f"{datetime.now():%Y-%m-%d %H:%M}",
        "demo": False,
        "current": {
            "temp": current.get("temperature_2m"),
            "humidity": current.get("relative_humidity_2m"),
            "text": _WMO_TEXT.get(current.get("weather_code"), ""),
            "wind_scale": days[0]["wind_scale"] if days else 1,
        },
        "days": days,
    }


def _demo_weather(location: dict[str, Any], farm_name: str) -> dict[str, Any]:
    """断网兜底：一组贴近华南冬季的演示天气，保证页面可演示。"""
    base = [
        ("小雨", 20, 15, 86, 2, 3),
        ("多云", 27, 17, 74, 0, 2),
        ("阴", 27, 17, 78, 0, 2),
        ("小雨", 24, 16, 88, 6, 3),
        ("多云", 22, 14, 70, 0, 2),
        ("晴", 21, 13, 62, 0, 1),
        ("晴", 23, 15, 65, 0, 1),
    ]
    weekday = "一二三四五六日"
    days = []
    now = datetime.now()
    for idx, (text, tmax, tmin, hum, precip, wind) in enumerate(base):
        day = now.fromordinal(now.toordinal() + idx)
        days.append(
            {
                "date": f"{day:%Y-%m-%d}",
                "week": f"周{weekday[day.weekday()]}",
                "text": text,
                "temp_max": tmax,
                "temp_min": tmin,
                "humidity": hum if idx == 0 else None,
                "precip": float(precip),
                "wind_scale": wind,
            }
        )
    return {
        "farm_name": farm_name,
        "city": location["city"],
        "source": "demo",
        "updated_at": f"{datetime.now():%Y-%m-%d %H:%M}",
        "demo": True,
        "current": {"temp": 19.6, "humidity": 84, "text": "小雨", "wind_scale": 2},
        "days": days,
    }


def resolve_location(farm_name: str) -> dict[str, Any]:
    """按养殖场名称关键字匹配城市；未命中时用默认场区。"""
    name = farm_name or ""
    for location in LOCATIONS:
        if any(key in name for key in location["keywords"]):
            return location
    return DEFAULT_LOCATION


def resolve_location_by_text(text: str) -> dict[str, Any] | None:
    """从用户提问中识别城市/场区关键字，用于问诊自动带天气。"""
    content = text or ""
    for location in LOCATIONS:
        if any(key in content for key in location["keywords"]):
            return location
    for key, location in CITY_LOCATIONS.items():
        if key in content:
            return location
    return None


def get_weather(farm_name: str, location: dict[str, Any] | None = None) -> dict[str, Any]:
    """获取场区天气（带 30 分钟缓存与多源降级）。"""
    location = location or resolve_location(farm_name)
    cache_key = f"{location['city_key']}:{location['lat']}:{location['lon']}"
    cached = _cache.get(cache_key)
    if cached and time.time() - cached[0] < settings.WEATHER_CACHE_TTL:
        data = dict(cached[1])
        data["farm_name"] = farm_name
        return data

    provider = (settings.WEATHER_PROVIDER or "auto").lower()
    fetchers = []
    if provider in ("auto", "open-meteo"):
        fetchers.append(_fetch_open_meteo)
    if provider in ("auto", "itboy"):
        fetchers.append(_fetch_itboy)

    data: dict[str, Any] | None = None
    for fetcher in fetchers:
        try:
            data = fetcher(location)
            break
        except Exception:  # noqa: BLE001 —— 依次降级
            continue
    if data is None:
        data = _demo_weather(location, farm_name)
    else:
        data["farm_name"] = farm_name
    _cache[cache_key] = (time.time(), data)
    return data


def weather_context_text(
    farm_name: str, days: int = 3, location: dict[str, Any] | None = None
) -> str:
    """把天气与风险压缩成一段提示词文本，供问答注入。"""
    from core.weather_risk import assess

    weather = get_weather(farm_name, location=location)
    result = assess(weather)
    lines = [
        f"场区：{farm_name}（{weather['city']}）",
        f"当前：{weather['current'].get('text') or '—'} {weather['current'].get('temp') or '—'}℃，"
        f"湿度 {weather['current'].get('humidity') or '—'}%",
    ]
    for item in result["days"][:days]:
        lines.append(
            f"{item['date']} {item['text']} {item['temp_min']}~{item['temp_max']}℃"
            f" 风险：{item['label']}"
            + (f"（{'、'.join(item['diseases'])}）" if item["diseases"] else "")
        )
    lines.append("综合风险：" + result["label"])
    if result["advice_short"]:
        lines.append("防控提示：" + "；".join(result["advice_short"]))
    return "\n".join(lines)
