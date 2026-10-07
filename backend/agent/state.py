"""Agent 状态结构（对应《详细实施方案》3.1 阶段 2 的 Agent State 设计）。

字段：用户 query、改写 query 列表、检索结果、答案、sources、循环次数。
"""
from typing import TypedDict


class AgentState(TypedDict, total=False):
    query: str                     # 用户原始问题（当前轮追问）
    history: list[dict]            # 最近对话历史 [{role, content}]，用于多轮指代消解与生成
    standalone_query: str          # 结合历史消解指代词后的独立问题（供图谱通道检索）
    rewritten_queries: list[str]   # Query 理解 Agent 改写后的多路召回 Query
    retrieval_results: list[dict]  # 检索 Agent 的召回结果（向量 + 图谱）
    graph_context: str             # 图谱子图上下文文本（阶段 3，可空）
    answer: str                    # 生成 Agent 的最终答案
    sources: list[dict]            # 溯源 Agent 标注的知识来源
    loop_count: int                # 评估循环次数（≤ EVAL_MAX_LOOPS）
    eval_result: dict              # 评估 Agent 打分结果 {relevance, sufficiency}
    passed: bool                   # 评估是否通过（达标或超限时为 True）
