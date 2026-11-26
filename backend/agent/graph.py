"""LangGraph 工作流：Query 理解（改写）→ 检索（向量 + 图谱双通道）→ 评估循环 → 生成 → 溯源。

- 检索：向量多路召回 + bge-reranker 精排，叠加图谱子图通道（图谱为空自动降级）。
- 评估：相关性 / 充分度打分，不达标则改写着重回检索（≤ EVAL_MAX_LOOPS），可由
  EVAL_LOOP_ENABLED 关闭（降级）。流式接口走 prepare/stream_generate/finish 线性链路，
  同样携带图谱上下文，但不做循环。

运行：python -m scripts.agent_chat "你的问题"
"""
import base64
import re
from datetime import datetime
from pathlib import Path

from core.config import settings
from core.llm import get_client, get_vision_client
from data_pipeline.retriever import retrieve_multi
from knowledge_graph import retriever as graph_retriever
from .state import AgentState

# ---- Query 理解 ----
_REWRITE_PROMPT = (
    "你是一名鹅养殖疫病问答检索助手。请把下面这个问题改写成 3 个更利于检索的独立搜索查询，"
    "每个查询一行，不要编号，不要多余文字。\n问题：{q}"
)

# 带历史时：要求补全指代词（它/这个病/上面说的），输出可独立检索的完整查询
_REWRITE_WITH_HISTORY_PROMPT = (
    "你是一名鹅养殖疫病问答检索助手。下面是用户与助手最近的对话：\n{history}\n\n"
    "请结合对话历史，把用户的最后一个问题改写成 3 个不依赖上下文即可理解的独立搜索查询，"
    "必须把其中的指代词（如“它”“这个病”“上面那种”）替换为对话中实际提到的鹅病或实体名称，"
    "每个查询一行，不要编号，不要多余文字。\n最后一个问题：{q}"
)


def _format_history(history: list[dict] | None) -> str:
    """把历史消息渲染为 prompt 中的对话文本。"""
    if not history:
        return ""
    lines = []
    for h in history:
        content = (h.get("content") or "").strip()
        if not content:
            continue
        who = "用户" if h.get("role") == "user" else "助手"
        lines.append(f"{who}：{content}")
    return "\n".join(lines)


def rewrite_queries(question: str, history: list[dict] | None = None) -> tuple[list[str], str]:
    """用 DeepSeek 把用户问题改写为多路检索 Query。

    带历史时要求消解指代词，返回 (去重后的检索 Query 列表, 独立问题)；
    独立问题取首个改写结果，供图谱通道使用。失败时降级为原文单路。
    """
    history_text = _format_history(history)
    prompt = (
        _REWRITE_WITH_HISTORY_PROMPT.format(history=history_text, q=question)
        if history_text
        else _REWRITE_PROMPT.format(q=question)
    )
    try:
        resp = get_client().chat.completions.create(
            model=settings.DEEPSEEK_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=200,
        )
        text = resp.choices[0].message.content or ""
        lines = [re.sub(r"^\d+[\.、)]\s*", "", ln).strip() for ln in text.splitlines()]
        queries = [ln for ln in lines if ln]
        standalone = queries[0] if (history_text and queries) else question
        # 有历史时消解后的完整查询排首位；无历史保持原文优先
        candidates = [*queries, question] if history_text else [question, *queries]
        merged: list[str] = []
        for q in candidates:
            if q not in merged and len(merged) < 3:
                merged.append(q)
        return merged, standalone
    except Exception:  # noqa: BLE001  —— 降级
        return [question], question


# ---- 节点 1：Query 理解 Agent ----
def query_understand(state: AgentState) -> AgentState:
    """意图识别 + Query 改写（多路召回 + 指代消解）。达到循环上限时不改写，直接沿用（避免无限发散）。"""
    queries, standalone = rewrite_queries(state["query"], state.get("history"))
    state["rewritten_queries"] = queries
    state["standalone_query"] = standalone
    return state


# ---- 节点 2：检索 Agent ----
def retrieve(state: AgentState) -> AgentState:
    """双通道召回：向量（多 Query + 精排） + 图谱子图。图谱未命中/为空自动跳过。"""
    state["retrieval_results"] = retrieve_multi(
        state["rewritten_queries"], top_k=settings.TOP_K
    )
    # 图谱实体查询对指代词敏感，追问时用消解后的独立问题
    hit = graph_retriever.retrieve_graph(state.get("standalone_query") or state["query"])
    state["graph_context"] = hit["text"] if hit else ""
    return state


# ---- 节点 5：评估 Agent（阶段 3 M3）----
_EVAL_PROMPT = (
    "你是问答质量评估员。根据下面的问题与检索上下文，分别对「检索相关性」（上下文是否贴合问题）"
    '和「信息充分度」（能否支撑完整回答）打 0-5 整数分。只输出 JSON，形如 '
    '{"relevance":0,"sufficiency":0}。\n问题：{q}\n上下文：{ctx}'
)


def _llm_eval(question: str, context: str) -> dict:
    """DeepSeek 打分 relevance / sufficiency（0-5）。解析失败降级为通过（各 3 分）。"""
    try:
        resp = get_client().chat.completions.create(
            model=settings.DEEPSEEK_MODEL,
            messages=[{"role": "user", "content": _EVAL_PROMPT.format(q=question, ctx=context[:1200])}],
            temperature=0.0,
            max_tokens=30,
        )
        text = (resp.choices[0].message.content or "").strip()
        nums = [int(x) for x in re.findall(r"\d+", text)]
        if len(nums) >= 2:
            return {"relevance": max(0, min(5, nums[0])), "sufficiency": max(0, min(5, nums[1]))}
    except Exception:  # noqa: BLE001 —— 降级通过
        pass
    return {"relevance": 3, "sufficiency": 3}


def evaluate(state: AgentState) -> AgentState:
    """相关性/充分度打分，判定是否达标。开关关闭时跳过评估直接通过（降级）。"""
    if not settings.EVAL_LOOP_ENABLED:
        state["eval_result"] = {"relevance": -1, "sufficiency": -1, "disabled": True}
        state["passed"] = True
        return state
    ctx = state.get("graph_context", "") or ""
    ctx += "\n".join(r["document"][:120] for r in state["retrieval_results"])
    score = _llm_eval(state["query"], ctx)
    state["eval_result"] = score
    state["passed"] = score["relevance"] >= 3 and score["sufficiency"] >= 3
    return state


# ---- 节点 0：循环重试 ----
def retry(state: AgentState) -> AgentState:
    """评估未达标时进入：循环次数 +1，交由 query_understand 改写重检索。"""
    state["loop_count"] = state.get("loop_count", 0) + 1
    return state


# ---- 节点 3：生成 Agent ----
def generate(state: AgentState) -> AgentState:
    """基于检索结果（向量 + 图谱）与多轮历史，调用 DeepSeek 生成答案。"""
    resp = get_client().chat.completions.create(
        model=settings.DEEPSEEK_MODEL,
        messages=build_messages(state),
        temperature=0.3,
    )
    state["answer"] = resp.choices[0].message.content
    return state


# ---- 节点 4：溯源 Agent ----
def trace_sources(state: AgentState) -> AgentState:
    """为答案标注知识来源。"""
    state["sources"] = [
        {"doc": r["metadata"]["doc"], "index": r["metadata"]["index"], "distance": r["distance"]}
        for r in state["retrieval_results"]
    ]
    return state


def build_graph():
    """编排节点并编译 LangGraph 图（含评估循环条件边）。"""
    from langgraph.graph import END, START, StateGraph

    g = StateGraph(AgentState)
    g.add_node("query_understand", query_understand)
    g.add_node("retrieve", retrieve)
    g.add_node("generate", generate)
    g.add_node("evaluate", evaluate)
    g.add_node("retry", retry)
    g.add_node("trace_sources", trace_sources)

    g.add_edge(START, "query_understand")
    g.add_edge("query_understand", "retrieve")
    g.add_edge("retrieve", "generate")
    g.add_edge("generate", "evaluate")

    def route(state: AgentState) -> str:
        # 开关关闭 / 达标 / 超限 → 溯源出答案；否则改写重检索
        if not settings.EVAL_LOOP_ENABLED or state.get("passed"):
            return "trace_sources"
        if state.get("loop_count", 0) >= settings.EVAL_MAX_LOOPS:
            return "trace_sources"
        return "retry"

    g.add_conditional_edges("evaluate", route, ["retry", "trace_sources"])
    g.add_edge("retry", "query_understand")
    g.add_edge("trace_sources", END)
    return g.compile()


agent = build_graph()


def run(query: str) -> AgentState:
    """执行完整问答流程（含评估循环），返回最终 AgentState。"""
    return agent.invoke({"query": query, "loop_count": 0})


# ---- 流式问答（接口层使用，避免等完整答案再返回）----

def prepare(question: str, history: list[dict] | None = None, weather_context: str = "") -> AgentState:
    """理解 + 检索（同步执行，结果喂给 stream_generate）。流式链路不做评估循环。

    history 为该会话最近若干轮 [{role, content}]，用于追问指代消解与多轮生成；
    weather_context 为场区天气与风险文本，非空时注入生成提示词，让建议与天气联动。
    """
    state: AgentState = {
        "query": question,
        "history": history or [],
        "loop_count": 0,
        "weather_context": weather_context,
    }
    query_understand(state)
    retrieve(state)
    return state


# ---- 急症预警：命中任一信号词即在前端展示红色警示条 ----
_EMERGENCY_KEYWORDS = (
    # 急性传染病名
    "禽流感", "流感", "小鹅瘟", "鸭瘟", "瘟", "副黏病毒", "副粘病毒", "新城疫",
    # 死亡类信号
    "死亡", "死鹅", "死禽", "死了一批", "死好多", "大批死",
    # 神经与重症症状
    "扭颈", "转圈", "角弓反张", "抽搐", "瘫痪", "头颈肿胀", "呼吸困难", "张口呼吸",
    # 出血类症状
    "血便", "拉血", "便血", "带血",
)


def detect_emergency(text: str) -> bool:
    """检测问题（或图片识别结果）中是否包含急性疫情信号词。"""
    if not text:
        return False
    return any(k in text for k in _EMERGENCY_KEYWORDS)


_SYSTEM_RULES = (
    "你是一名鹅养殖疫病风险评估助手。请先判断问题类型：\n"
    "1. 鹅养殖、疫病、症状、用药、免疫、生物安全等专业问题：必须仅根据下面的参考资料回答，"
    "不要编造资料之外的内容；如果资料确实不足以回答，再明确说明。\n"
    "2. 问候、闲聊、当前时间、使用帮助、常识等与专业知识无关的问题："
    "不必依赖参考资料，直接用简洁友好的语气回答即可（当前系统时间：{now}）。\n"
    "3. 若问题涉及急性传染病、家禽大批死亡等紧急疫情，回答开头必须先给出应急提示，"
    "包含：立即隔离病鹅、病死禽不得随意丢弃或出售、尽快联系当地兽医或动物疫控部门。\n"
    "4. 若下方提供了「场区天气与风险」，回答防控建议时应结合近期天气给出针对性提醒"
    "（如降温注意保温、降雨高湿防球虫），但不要生硬复述天气数据。\n"
    "回答请使用纯文本，不要使用 Markdown 格式（如 **、*、#、- 等符号），"
    "直接以自然语句和数字序号表述。若用户追问上一轮提到的内容，请结合对话历史连贯作答。"
)


def build_messages(state: AgentState) -> list[dict]:
    """构造多轮 chat messages：system（规则 + 参考资料）+ 最近历史 + 当前问题。"""
    blocks = [
        f"[来源：{r['metadata']['doc']}]\n{r['document']}" for r in state["retrieval_results"]
    ]
    if state.get("graph_context"):
        blocks.append(state["graph_context"])
    context = "\n\n".join(blocks)
    now = datetime.now().strftime("%Y年%m月%d日 %H:%M")
    weather_block = ""
    if state.get("weather_context"):
        weather_block = f"\n\n场区天气与风险：\n{state['weather_context']}"
    messages: list[dict] = [
        {"role": "system", "content": _SYSTEM_RULES.format(now=now) + weather_block + f"\n\n参考资料：\n{context}"}
    ]
    for h in state.get("history") or []:
        content = (h.get("content") or "").strip()
        if not content:
            continue  # 纯图片消息等空内容跳过，避免出现空轮次
        messages.append(
            {"role": "user" if h.get("role") == "user" else "assistant", "content": content}
        )
    messages.append({"role": "user", "content": state["query"]})
    return messages


def stream_generate(state: AgentState):
    """流式调用 DeepSeek，逐 token 产出（LLM 开始返回即有首 token）。"""
    stream = get_client().chat.completions.create(
        model=settings.DEEPSEEK_MODEL,
        messages=build_messages(state),
        temperature=0.3,
        stream=True,
    )
    parts: list[str] = []
    for chunk in stream:
        delta = chunk.choices[0].delta.content if chunk.choices else None
        if delta:
            parts.append(delta)
            yield delta
    state["answer"] = "".join(parts)


def finish(state: AgentState) -> list[dict]:
    """溯源标注，返回 sources。"""
    trace_sources(state)
    return state["sources"]


def identify_disease(image_path: str) -> str:
    """上传鹅病图片，调用视觉模型识别疾病类型及症状描述，返回文本。"""
    if not settings.VISION_ENABLED or not settings.VISION_API_KEY:
        raise RuntimeError("图片识别未启用：请在 .env 配置 VISION_API_KEY 并设置 VISION_ENABLED=true")

    client = get_vision_client()
    # 按真实扩展名设置 MIME，避免 png/webp 被误标为 jpeg
    mime_map = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
                ".webp": "image/webp", ".gif": "image/gif"}
    suffix = Path(image_path).suffix.lower()
    mime = mime_map.get(suffix, "image/jpeg")
    with open(image_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")

    prompt = (
        "你是一名资深鹅养殖疫病诊断专家。请仔细观察图片中鹅只的外观与症状，"
        "如果图片确实是鹅或病禽，请按以下结构用中文回答：\n"
        "1. 观察到的症状（精神状态、羽毛、眼睛、口鼻、排泄物、行动姿态等）\n"
        "2. 初步判断的可能疾病（列出 1-3 种可能性并说明依据，不要绝对化）\n"
        "3. 紧急处理与就医建议（隔离、消毒、联系兽医等）\n"
        "如果图片内容不是鹅/禽，或无法据此判断，请直接说明，不要编造疾病。\n"
        "请使用纯文本回答，不要使用 Markdown 格式符号（如 **、*、# 等），用数字序号表述。"
    )
    resp = client.chat.completions.create(
        model=settings.VISION_MODEL,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
                ],
            }
        ],
        temperature=0.3,
        max_tokens=700,
    )
    return resp.choices[0].message.content or "无法识别图片内容"
