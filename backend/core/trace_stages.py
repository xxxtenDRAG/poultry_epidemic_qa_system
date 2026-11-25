"""鹅全链路溯源阶段字典。

前端通过 GET /api/traceability/stages 获取；种子数据与接口共用，避免两边硬编码不一致。
"""

STAGES = [
    {
        "key": "incubation",
        "name": "孵化/鹅苗",
        "short": "孵化",
        "color": "#e6a23c",
        "description": "种蛋来源、孵化记录与雏鹅检疫",
    },
    {
        "key": "brooding",
        "name": "育雏",
        "short": "育雏",
        "color": "#67c23a",
        "description": "保温、开口、首免与成活率",
    },
    {
        "key": "growing",
        "name": "生长育成",
        "short": "育成",
        "color": "#409eff",
        "description": "转群、密度、日粮与体重",
    },
    {
        "key": "health",
        "name": "防疫与健康",
        "short": "防疫",
        "color": "#9c27b0",
        "description": "免疫、抗体检测、巡栏与隔离处置",
    },
    {
        "key": "outbound",
        "name": "出栏检疫",
        "short": "出栏",
        "color": "#00bcd4",
        "description": "出栏申报、检疫合格与运输准备",
    },
    {
        "key": "slaughter",
        "name": "屠宰加工",
        "short": "屠宰",
        "color": "#ff9800",
        "description": "屠宰批次、宰前宰后检验与加工",
    },
    {
        "key": "quality",
        "name": "质检分级",
        "short": "质检",
        "color": "#f56c6c",
        "description": "产品分级、兽药残留与合格证明",
    },
    {
        "key": "coldchain",
        "name": "冷链物流",
        "short": "冷链",
        "color": "#607d8b",
        "description": "冷库入库、运输温度与交接",
    },
    {
        "key": "sales",
        "name": "终端销售",
        "short": "销售",
        "color": "#1f6f54",
        "description": "销售渠道、终端门店与批次去向",
    },
]

STAGE_MAP = {item["key"]: item for item in STAGES}
STAGE_ORDER = {item["key"]: index for index, item in enumerate(STAGES)}
VALID_STAGES = tuple(STAGE_ORDER)


def stage_meta(key: str) -> dict:
    """返回阶段元数据；未知阶段使用灰色兜底，避免接口 500。"""
    return STAGE_MAP.get(
        key,
        {
            "key": key,
            "name": key or "未知环节",
            "short": key or "未知",
            "color": "#909399",
            "description": "",
        },
    )
