"""Agent 状态结构（对应《详细实施方案》3.1 阶段 2 的 Agent State 设计）。

字段：用户 query、改写 query 列表、检索结果、答案、sources、循环次数。
"""
from typing import TypedDict


class AgentState(TypedDict, total=False):
    query: str                     # 用户原始问题
    rewritten_queries: list[str]   # Query 理解 Agent 改写后的多路召回 Query
    retrieval_results: list[dict]  # 检索 Agent 的召回结果（向量 + 图谱）
    answer: str                    # 生成 Agent 的最终答案
    sources: list[dict]            # 溯源 Agent 标注的知识来源
    loop_count: int                # 评估循环次数（≤ 3）
