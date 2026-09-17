"""LangGraph 最小工作流：Query 理解 → 检索 → 生成 → 溯源（阶段 1，无评估循环）。

运行：python -m scripts.agent_chat "你的问题"
"""
from openai import OpenAI

from core.config import settings
from data_pipeline.embed import embed_texts
from data_pipeline.store import search as vector_search
from .state import AgentState

_client: OpenAI | None = None


def get_client() -> OpenAI:
    """DeepSeek 客户端（OpenAI 兼容接口，惰性初始化）。"""
    global _client
    if _client is None:
        _client = OpenAI(api_key=settings.DEEPSEEK_API_KEY, base_url=settings.DEEPSEEK_BASE_URL)
    return _client


# ---- 节点 1：Query 理解 Agent ----
def query_understand(state: AgentState) -> AgentState:
    """意图识别 + Query 改写。

    阶段 1：原文直通（单路召回）。
    阶段 2：增加改写生成多路 Query（多 Query 召回）。
    """
    state["rewritten_queries"] = [state["query"]]
    return state


# ---- 节点 2：检索 Agent ----
def retrieve(state: AgentState) -> AgentState:
    """向量检索（双通道中的向量通道；图谱通道阶段 3 接入）。"""
    results = []
    for q in state["rewritten_queries"]:
        emb = embed_texts([q])[0]
        results.extend(vector_search(emb, top_k=settings.TOP_K))

    # 多路召回按 文档+块号 去重，再取 Top-K
    seen = set()
    dedup: list[dict] = []
    for r in results:
        key = (r["metadata"]["doc"], r["metadata"]["index"])
        if key not in seen:
            seen.add(key)
            dedup.append(r)
    state["retrieval_results"] = dedup[: settings.TOP_K]
    return state


# ---- 节点 3：生成 Agent ----
def generate(state: AgentState) -> AgentState:
    """基于检索结果构造 Prompt，调用 DeepSeek 生成答案。"""
    context = "\n\n".join(
        f"[来源：{r['metadata']['doc']}]\n{r['document']}" for r in state["retrieval_results"]
    )
    prompt = (
        "你是一名鹅养殖疫病风险评估助手。请仅根据下面的参考资料回答问题，"
        "不要编造资料之外的内容；如果资料不足以回答，请明确说明。\n\n"
        f"参考资料：\n{context}\n\n问题：{state['query']}\n"
    )
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
    """编排 4 个节点，编译 LangGraph 图。"""
    from langgraph.graph import END, START, StateGraph

    g = StateGraph(AgentState)
    g.add_node("query_understand", query_understand)
    g.add_node("retrieve", retrieve)
    g.add_node("generate", generate)
    g.add_node("trace_sources", trace_sources)

    g.add_edge(START, "query_understand")
    g.add_edge("query_understand", "retrieve")
    g.add_edge("retrieve", "generate")
    g.add_edge("generate", "trace_sources")
    g.add_edge("trace_sources", END)
    return g.compile()


agent = build_graph()


def run(query: str) -> AgentState:
    """执行完整问答流程，返回最终 AgentState。"""
    return agent.invoke({"query": query, "loop_count": 0})


# ---- 流式问答（接口层使用，避免等完整答案再返回）----

def prepare(question: str) -> AgentState:
    """理解 + 检索（同步执行，结果喂给 stream_generate）。"""
    state: AgentState = {"query": question, "loop_count": 0}
    query_understand(state)
    retrieve(state)
    return state


def build_prompt(state: AgentState) -> str:
    """构造生成 Prompt（与 generate 节点一致）。"""
    context = "\n\n".join(
        f"[来源：{r['metadata']['doc']}]\n{r['document']}" for r in state["retrieval_results"]
    )
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
