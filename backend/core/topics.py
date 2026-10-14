"""提问维度（主题）定义与规则识别。

用途：
- 会话历史按「提问维度」归档与筛选
- 对话页按维度给出快捷提问模板（前端从 GET /api/sessions/overview 取）

识别走关键词命中计分，不调用 LLM：历史列表要快、也要能离线跑。
维度只在这里定义一份，避免前后端各维护一套。
新增维度往 TOPICS 里加一项即可，前端会自动多出筛选标签与提问卡片。
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Topic:
    """一个提问维度。"""

    id: str
    label: str
    keywords: tuple[str, ...]    # 命中即计分的关键词
    questions: tuple[str, ...]   # 该维度的快捷提问模板


TOPICS: tuple[Topic, ...] = (
    Topic(
        id="diagnosis",
        label="疫病诊断与鉴别",
        keywords=(
            "症状", "诊断", "鉴别", "确诊", "剖检", "病变", "潜伏期", "发病率", "死亡率",
            "拉稀", "腹泻", "抽搐", "瘫痪", "扭颈", "精神沉郁", "肿胀", "呼吸困难", "头颈",
            "治疗", "发病", "传染", "病原",
            # 常见鹅病名称：问「某某病怎么防」时主题仍落在具体疫病上
            "小鹅瘟", "鹅瘟", "鸭瘟", "副黏", "副粘", "禽流感", "流感", "新城疫",
            "大肠杆菌", "浆膜炎", "球虫", "曲霉", "副伤寒", "霍乱", "沙门氏",
            "呼肠孤", "腺病毒", "坦布苏", "鸭疫", "痛风", "啄羽", "软脚",
        ),
        questions=(
            "雏鹅拉稀、精神沉郁可能是什么病？",
            "小鹅瘟和鹅副黏病毒病怎么鉴别？",
            "病死鹅剖检重点看哪些病变？",
        ),
    ),
    Topic(
        id="vaccine",
        label="免疫与疫苗",
        keywords=("疫苗", "免疫", "接种", "首免", "二免", "抗体", "免疫程序", "滴鼻", "点眼", "皮下注射"),
        questions=(
            "雏鹅首免日龄怎么安排？",
            "种鹅产蛋前的免疫程序是什么？",
            "疫苗接种后免疫失败有哪些常见原因？",
        ),
    ),
    Topic(
        id="biosecurity",
        label="消毒与生物安全",
        keywords=(
            "消毒", "生物安全", "隔离", "无害化", "粪污", "灭蚊", "灭鼠", "净道", "污道", "带鹅消毒",
            "防控", "防治", "预防", "净化",
        ),
        questions=(
            "鹅舍日常消毒用什么药、怎么轮换？",
            "进出鹅场的生物安全流程怎么做？",
            "病死鹅无害化处理有哪些合规做法？",
        ),
    ),
    Topic(
        id="medication",
        label="用药与兽药规范",
        keywords=("用药", "药量", "剂量", "拌料", "饮水给药", "抗菌药", "抗生素", "驱虫", "休药期", "兽药"),
        questions=(
            "鹅常用抗菌药怎么选、剂量怎么算？",
            "产蛋期用药要注意什么休药期？",
            "驱虫药怎么安排才能避免反复感染？",
        ),
    ),
    Topic(
        id="husbandry",
        label="饲养管理与孵化",
        keywords=("育雏", "保温", "温度", "湿度", "密度", "通风", "光照", "孵化", "种蛋", "开食", "开水", "垫料"),
        questions=(
            "育雏期的温湿度与密度怎么控制？",
            "种蛋孵化的温湿度与翻蛋怎么安排？",
            "雏鹅开水开食的操作要点是什么？",
        ),
    ),
    Topic(
        id="nutrition",
        label="营养代谢与中毒",
        keywords=("营养", "饲料", "维生素", "微量元素", "钙磷", "痛风", "霉菌毒素", "中毒", "食盐", "蛋白"),
        questions=(
            "雏鹅痛风的发病原因和防控要点？",
            "鹅霉菌毒素中毒怎么处理？",
            "种鹅产蛋期需要补哪些营养？",
        ),
    ),
    Topic(
        id="emergency",
        label="疫情处置与法规",
        keywords=("疫情", "报告", "扑杀", "封锁", "应急", "法规", "动物防疫法", "检疫", "出栏", "调运"),
        questions=(
            "怀疑急性疫情时第一时间该做什么？",
            "疫情报告与封锁处置的流程是什么？",
            "鹅调运与检疫需要哪些合规手续？",
        ),
    ),
    Topic(
        id="risk",
        label="风险评估与分级",
        keywords=("风险", "评估", "分级", "预警", "监测", "排查", "整改", "评分"),
        questions=(
            "鹅场疫病风险评估怎么开展？",
            "风险分级后不同等级怎么处置？",
            "日常监测与预警指标有哪些？",
        ),
    ),
)

# 未命中任何维度时的兜底维度，保证每个会话都有可筛选的标签
FALLBACK_TOPIC_ID = "general"
FALLBACK_TOPIC_LABEL = "综合问答"
FALLBACK_QUESTIONS = (
    "鹅养殖常见疫病有哪些？",
    "新手养鹅需要重点注意什么？",
    "如何制定鹅场全年防疫计划？",
)

# 单个会话最多归入的维度数：命中太多会让标签失去区分度
MAX_TOPICS_PER_SESSION = 2
# 参与打分的文本上限（字符），避免超长会话拖慢列表接口
SCORE_TEXT_LIMIT = 4000


def detect_topics(text: str) -> list[str]:
    """按关键词命中识别文本所属的提问维度，返回维度 id（得分高者在前）。

    长关键词权重更高（4 字及以上记 2 分），避免「温度」这类短词盖过具体主题；
    没有任何命中时返回兜底维度，保证会话在历史页始终可被筛选到。
    """
    if not text:
        return [FALLBACK_TOPIC_ID]

    sample = text[:SCORE_TEXT_LIMIT]
    scored: list[tuple[int, int, str]] = []
    for order, topic in enumerate(TOPICS):
        score = sum(2 if len(word) >= 4 else 1 for word in topic.keywords if word in sample)
        if score > 0:
            scored.append((score, order, topic.id))

    if not scored:
        return [FALLBACK_TOPIC_ID]

    # 同分时按 TOPICS 定义顺序，保证结果稳定
    scored.sort(key=lambda item: (-item[0], item[1]))
    return [item[2] for item in scored[:MAX_TOPICS_PER_SESSION]]
