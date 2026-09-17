"""知识图谱构建（阶段 3 M1）：LLM 抽三元组 → NetworkX 构图 → Louvain 社区检测 → 落盘 JSON。

用法（backend 目录、venv 激活）：
    python -m scripts.build_graph [--rebuild]   # 重新抽取 + 构图 + 保存

数据来源：ChromaDB 中全部知识块。
产物：<项目根>/data/knowledge_graph.json（nodes + edges 两个数组）。

降级原则：某块三元组解析失败则跳过该块并记日志，不阻塞整条流水线。
"""
import argparse
import json
import re
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from core.config import settings  # noqa: E402
from core.llm import get_client  # noqa: E402
from data_pipeline.store import get_collection  # noqa: E402

# 固定本体：实体类型 / 关系类型（中文标签，与页面展示一致）
ENTITY_TYPES = ["疾病", "病原", "症状", "药物", "疫苗", "宿主", "传播途径", "防控"]
RELATION_TYPES = {"引起", "表现为", "预防", "治疗", "易感", "传播"}
MAX_TRIPLES_PER_CHUNK = 5

_EXTRACT_PROMPT = (
    "你是鹅养殖疫病知识图谱构建助手。从下面知识块中抽取最多 {max} 条关系三元组 (头实体, 关系, 尾实体)。"
    "实体类型仅限：{entity_types}；关系仅限：{relation_types}。"
    '严格输出 JSON 数组，形如 [{{"head": "...", "rel": "...", "tail": "..."}}]，不要输出其它文字。\n'
    "知识块：\n{chunk}"
)


def _extract_triples(chunk: str) -> list[dict]:
    """用 DeepSeek 从单个知识块抽取三元组，解析失败返回空（降级跳过）。"""
    prompt = _EXTRACT_PROMPT.format(
        max=MAX_TRIPLES_PER_CHUNK,
        entity_types="、".join(ENTITY_TYPES),
        relation_types="、".join(RELATION_TYPES),
        chunk=chunk[:512],
    )
    try:
        resp = get_client().chat.completions.create(
            model=settings.DEEPSEEK_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=500,
        )
        text = (resp.choices[0].message.content or "").strip()
        # 去掉 ```json 代码块包裹
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.MULTILINE).strip()
        data = json.loads(text)
        if not isinstance(data, list):
            return []
        triples = []
        for t in data:
            if isinstance(t, dict) and t.get("head") and t.get("tail") and t.get("rel"):
                triples.append(
                    {
                        "head": str(t["head"]).strip(),
                        "rel": str(t["rel"]).strip(),
                        "tail": str(t["tail"]).strip(),
                    }
                )
        return triples
    except Exception as e:  # noqa: BLE001 —— 单块失败降级跳过
        print(f"[build_graph] 三元组解析失败，跳过该块：{e}")
        return []


def build() -> None:
    col = get_collection()
    res = col.get(include=["documents", "metadatas"])
    chunks = res["documents"]
    metas = res["metadatas"]
    if not chunks:
        print("[build_graph] ChromaDB 为空，无知识块可抽三元组。")
        return

    import networkx as nx

    g = nx.DiGraph()
    skipped = 0
    for i, (doc, meta) in enumerate(zip(chunks, metas)):
        doc_name = meta.get("doc", "unknown")
        triples = _extract_triples(doc)
        if not triples:
            skipped += 1
            continue
        # 节点带 type/docs[]，节点 type 由关系语义推断（head 类型不易确定，此处简化用动态标签）
        for t in triples:
            if not g.has_node(t["head"]):
                g.add_node(t["head"], type=_infer_type(t, "head"), community=-1, docs=[])
            if not g.has_node(t["tail"]):
                g.add_node(t["tail"], type=_infer_type(t, "tail"), community=-1, docs=[])
            if doc_name not in g.nodes[t["head"]]["docs"]:
                g.nodes[t["head"]]["docs"].append(doc_name)
            if doc_name not in g.nodes[t["tail"]]["docs"]:
                g.nodes[t["tail"]]["docs"].append(doc_name)
            g.add_edge(t["head"], t["tail"], relation=t["rel"])

    # Louvain 社区检测（无向视角），社区号写回节点属性
    try:
        import community as community_louvain

        partition = community_louvain.best_partition(g.to_undirected())
        for node, comm in partition.items():
            g.nodes[node]["community"] = comm
    except Exception as e:  # noqa: BLE001 —— 社区检测失败则保留 -1
        print(f"[build_graph] 社区检测失败（保留 -1）：{e}")

    # 落盘 JSON（nodes + edges 两个数组）
    nodes = [
        {"id": n, "type": g.nodes[n].get("type", ""), "community": g.nodes[n].get("community", -1),
         "docs": g.nodes[n].get("docs", [])}
        for n in g.nodes
    ]
    edges = [
        {"source": u, "target": v, "relation": g.edges[u, v].get("relation", "")}
        for u, v in g.edges
    ]
    data = {"nodes": nodes, "edges": edges}
    out = Path(settings.graph_data_file)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    community_count = len({n["community"] for n in nodes if n["community"] >= 0})
    print(f"[build_graph] 完成：块 {len(chunks)}（跳过 {skipped}）→ 节点 {len(nodes)} / 边 {len(edges)} / 社区 {community_count}")
    print(f"[build_graph] 已写入 {out}")


def _infer_type(triple: dict, side: str) -> str:
    """依据三元组关系与实体位置，按固定本体启发式推断实体类型。

    关系语义映射（head→rel→tail）：
      引起: 病原 → 疾病
      表现为: 疾病 → 症状
      预防: 疫苗/防控 → 疾病
      治疗: 药物 → 疾病
      易感: 宿主 → 疾病
      传播: 疾病 → 传播途径
    该推断尽可能贴近本体的典型方向，不强求 100% 精确。
    """
    rel = triple["rel"]
    mapping = {
        "head": {
            "引起": "病原", "表现为": "疾病", "预防": "疫苗", "治疗": "药物",
            "易感": "宿主", "传播": "疾病",
        },
        "tail": {
            "引起": "疾病", "表现为": "症状", "预防": "疾病", "治疗": "疾病",
            "易感": "疾病", "传播": "传播途径",
        },
    }
    return mapping[side].get(rel, "疾病")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--rebuild", action="store_true", help="强制重建")
    ap.parse_args()
    build()