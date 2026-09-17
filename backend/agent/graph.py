"""LangGraph 工作流：Query 理解（改写）→ 检索（向量 + 图谱双通道）→ 评估循环 → 生成 → 溯源。

- 检索：向量多路召回 + bge-reranker 精排，叠加图谱子图通道（图谱为空自动降级）。
- 评估：相关性 / 充分度打分，不达标则改写着重回检索（≤ EVAL_MAX_LOOPS），可由
  EVAL_LOOP_ENABLED 关闭（降级）。流式接口走 prepare/stream_generate/finish 线性链路，
  同样携带图谱上下文，但不做循环。

运行：python -m scripts.agent_chat "你的问题"
"""
import re

from core.config import settings
from core.llm import get_client
from data_pipeline.retriever import retrieve_multi
from knowledge_graph import retriever as graph_retriever
from .state import AgentState

# ---- Query 理解 ----
_REWRITE_PROMPT = (
    "你是一名鹅养殖疫病问答检索助手。请把下面这个问题改写成 3 个更利于检索的独立搜索查询，"
    "每个查询一行，不要编号，不要多余文字。\n问题：{q}"
)


def rewrite_queries(question: str) -> list[str]:
    """用 DeepSeek 把用户问题改写为 3 个检索 Query（多路召回）。

    失败时降级为原文单路（项目约定：复杂模块必须可关闭）。
    """
    try:
        resp = get_client().chat.completions.create(
            model=settings.DEEPSEEK_MODEL,
            messages=[{"role": "user", "content": _REWRITE_PROMPT.format(q=question)}],
            temperature=0.7,
            max_tokens=200,
        )
        text = resp.choices[0].message.content or ""
        lines = [re.sub(r"^\d+[\.、)]\s*", "", ln).strip() for ln in text.splitlines()]
        queries = [ln for ln in lines if ln]
        merged: list[str] = []
        for q in [question, *queries]:
            if q not in merged and len(merged) < 3:
                merged.append(q)
        return merged
    except Exception:  # noqa: BLE001  —— 降级
        return [question]


# ---- 节点 1：Query 理解 Agent ----
def query_understand(state: AgentState) -> AgentState:
    """意图识别 + Query 改写（多路召回）。达到循环上限时不改写，直接沿用（避免无限发散）。"""
    state["rewritten_queries"] = rewrite_queries(state["query"])
    return state


# ---- 节点 2：检索 Agent ----
def retrieve(state: AgentState) -> AgentState:
    """双通道召回：向量（多 Query + 精排） + 图谱子图。图谱未命中/为空自动跳过。"""
    state["retrieval_results"] = retrieve_multi(
        state["rewritten_queries"], top_k=settings.TOP_K
    )
    hit = graph_retriever.retrieve_graph(state["query"])
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
    """基于检索结果（向量 + 图谱）构造 Prompt，调用 DeepSeek 生成答案。"""
    prompt = build_prompt(state)
    resp = get_client().chat.completions.create(
        model=settings.DEEPSEEK_MODEL,
        messages=[{"role": "user", "content": prompt}],
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

def prepare(question: str) -> AgentState:
    """理解 + 检索（同步执行，结果喂给 stream_generate）。流式链路不做评估循环。"""
    state: AgentState = {"query": question, "loop_count": 0}
    query_understand(state)
    retrieve(state)
    return state


def build_prompt(state: AgentState) -> str:
    """构造生成 Prompt（与 generate 节点一致，含图谱上下文）。"""
    blocks = [
        f"[来源：{r['metadata']['doc']}]\n{r['document']}" for r in state["retrieval_results"]
    ]
    if state.get("graph_context"):
        blocks.append(state["graph_context"])
    context = "\n\n".join(blocks)
    return (
        "你是一名鹅养殖疫病风险评估助手。请仅根据下面的参考资料回答问题，"
        "不要编造资料之外的内容；如果资料不足以回答，请明确说明。\n\n"
        f"参考资料：\n{context}\n\n问题：{state['query']}\n"
    )


def stream_generate(state: AgentState):
    """流式调用 DeepSeek，逐 token 产出（LLM 开始返回即有首 token）。"""
    stream = get_client().chat.completions.create(
        model=settings.DEEPSEEK_MODEL,
        messages=[{"role": "user", "content": build_prompt(state)}],
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
