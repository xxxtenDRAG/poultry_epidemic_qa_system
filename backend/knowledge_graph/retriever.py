"""知识图谱检索（阶段 3 M2）：实体抽取 → 子图召回 → 供 Agent 双通道融合 / 前端可视化。

数据源：<项目根>/data/knowledge_graph.json（由 scripts/build_graph.py 生成）。
降级原则：图谱文件缺失/为空、实体抽取失败、未命中实体 → 自动跳过图谱通道（不影响主链路）。
"""
import json
import re
from functools import lru_cache
from pathlib import Path

import networkx as nx

from core.config import settings
from core.llm import get_client

_ENTITY_EXTRACT_PROMPT = (
    "从下面问题中抽取最重要的 1-3 个关键实体（疾病、病原、症状、药物、疫苗等），"
    '严格输出 JSON 数组，形如 ["实体A"]，词从问题原文中选取，不要解释。\n问题：{q}'
)


@lru_cache(maxsize=1)
def load_graph() -> "nx.DiGraph":
    """加载图谱 JSON 为 NetworkX 有向图（带 type / community / docs 节点属性）。"""
    g = nx.DiGraph()
    path = Path(settings.graph_data_file)
    if not path.exists():
        return g
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        for n in data.get("nodes", []):
            g.add_node(
                n["id"],
                type=n.get("type", ""),
                community=n.get("community", -1),
                docs=n.get("docs", []),
            )
        for e in data.get("edges", []):
            if g.has_node(e.get("source")) and g.has_node(e.get("target")):
                g.add_edge(e["source"], e["target"], relation=e.get("relation", ""))
    except Exception:  # noqa: BLE001 —— 加载失败降级为空图
        return nx.DiGraph()
    return g


def extract_entities(query: str) -> list[str]:
    """用 DeepSeek 从 query 抽取候选实体；失败降级为词表子串匹配。"""
    try:
        resp = get_client().chat.completions.create(
            model=settings.DEEPSEEK_MODEL,
            messages=[{"role": "user", "content": _ENTITY_EXTRACT_PROMPT.format(q=query)}],
            temperature=0.0,
            max_tokens=100,
        )
        text = (resp.choices[0].message.content or "").strip()
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.MULTILINE).strip()
        data = json.loads(text)
        if isinstance(data, list):
            ents = [str(x).strip() for x in data if isinstance(x, str) and x.strip()]
            if ents:
                return ents
    except Exception:  # noqa: BLE001 —— 降级为词表匹配
        pass
    # 词表子串匹配：query 中出现哪个节点 id，即命中哪个实体
    g = load_graph()
    return [n for n in g.nodes if n and n in query]


def _neighbors_subgraph(entity: str, hop: int = 1) -> list[dict]:
    """返回实体 hop 跳内子图的 {nodes, edges} 结构。"""
    g = load_graph()
    if entity not in g:
        return []
    if hop <= 0:
        reach = {entity}
    else:
        reach = {entity}
        frontier = {entity}
        for _ in range(hop):
            nxt = set(frontier)
            for n in frontier:
                nxt |= set(g.successors(n)) | set(g.predecessors(n))
            reach |= nxt
            frontier = nxt - reach
    sub = g.subgraph(reach)
    nodes = [
        {"id": n, "type": sub.nodes[n].get("type", ""), "community": sub.nodes[n].get("community", -1)}
        for n in sub.nodes
    ]
    edges = [
        {"source": u, "target": v, "relation": sub.edges[u, v].get("relation", "")}
        for u, v in sub.edges
    ]
    return [{"nodes": nodes, "edges": edges}]


def query_entity(entity: str) -> dict:
    """按单个实体查询子图（供前端 /api/graph/query 使用）。"""
    sub = _neighbors_subgraph(entity, settings.GRAPH_HOP)
    return {
        "entity": entity,
        "nodes": sub[0]["nodes"] if sub else [],
        "edges": sub[0]["edges"] if sub else [],
    }


def retrieve_graph(query: str) -> dict | None:
    """图谱通道召回：抽取实体 → 汇总各实体一跳子图，拼成子图上下文文本。

    返回 {text, entities, nodes, edges}；图谱为空或未命中实体时返回 None（自动降级）。
    """
    g = load_graph()
    if g.number_of_nodes() == 0:
        return None
    entities = extract_entities(query)
    if not entities:
        return None

    nodes: dict[str, dict] = {}
    edges: list[dict] = []
    matched: list[str] = []
    for ent in entities:
        if ent not in g:
            continue
        matched.append(ent)
        for node in g.neighbors(ent):
            nodes[node] = {"id": node, "type": g.nodes[node].get("type", ""),
                           "community": g.nodes[node].get("community", -1)}
            edges.append({"source": ent, "target": node, "relation": g.edges[ent, node].get("relation", "")})
        for node in g.predecessors(ent):
            nodes[node] = {"id": node, "type": g.nodes[node].get("type", ""),
                           "community": g.nodes[node].get("community", -1)}
            edges.append({"source": node, "target": ent, "relation": g.edges[node, ent].get("relation", "")})
        nodes[ent] = {"id": ent, "type": g.nodes[ent].get("type", ""),
                      "community": g.nodes[ent].get("community", -1)}
    if not matched:
        return None

    # 拼子图文本，作为生成上下文的一部分
    lines = []
    for e in edges:
        lines.append(f"{e['source']} -[{e['relation']}]-> {e['target']}")
    text = "知识图谱子图：\n" + "\n".join(lines)
    return {"text": text, "entities": matched, "nodes": list(nodes.values()), "edges": edges}


def get_overview() -> dict:
    """节点/边/社区统计（供 /api/graph/overview，可选）。"""
    g = load_graph()
    communities: dict[int, int] = {}
    for n in g.nodes:
        c = g.nodes[n].get("community", -1)
        if c >= 0:
            communities[c] = communities.get(c, 0) + 1
    return {
        "node_count": g.number_of_nodes(),
        "edge_count": g.number_of_edges(),
        "community_count": len(communities),
        "communities": [{"id": c, "size": s} for c, s in sorted(communities.items())],
    }


def get_entity_detail(entity: str) -> dict:
    """单个实体的完整详情：属性 + 关联关系列表（供前端点击节点展示）。"""
    g = load_graph()
    if entity not in g:
        return {"entity": entity, "found": False}
    node = g.nodes[entity]
    # 关联关系
    relations = []
    for succ in g.successors(entity):
        relations.append({
            "direction": "out",
            "relation": g.edges[entity, succ].get("relation", ""),
            "target": succ,
            "target_type": g.nodes[succ].get("type", "")
        })
    for pred in g.predecessors(entity):
        relations.append({
            "direction": "in",
            "relation": g.edges[pred, entity].get("relation", ""),
            "target": pred,
            "target_type": g.nodes[pred].get("type", "")
        })
    return {
        "entity": entity,
        "found": True,
        "type": node.get("type", ""),
        "community": node.get("community", -1),
        "docs": node.get("docs", []),
        "relations": relations
    }