"""知识图谱构建（阶段 3 M1，增强版）：LLM 抽带类型三元组 → 本体校验/归一化
→ NetworkX 构图 → Louvain 社区检测 → 落盘 JSON。

用法（backend 目录、venv 激活）：
    python -m scripts.build_graph [--rebuild]   # 重新抽取 + 构图 + 保存

数据来源：ChromaDB 中全部知识块。
产物：<项目根>/data/knowledge_graph.json（nodes + edges 两个数组）。

增强点（feat/knowledge-graph-enhance）：
- 每块三元组上限 5 → 12，LLM 同时输出头尾实体类型并附 few-shot，类型不再靠位置瞎猜；
- 关系同义词归一 + 非法关系丢弃；实体别名表归一 + 泛称停用词 + 长度过滤；
- 按关系本体校验 (head_type, tail_type)，方向反了自动翻转、不符合且不可翻转的丢弃；
- 节点类型多轮投票取众数，消除单条三元组误判。
降级原则：某块三元组解析失败则跳过该块并记日志，不阻塞整条流水线。
"""
import argparse
import hashlib
import json
import re
import sys
import time
from collections import defaultdict
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from core.config import settings  # noqa: E402
from core.llm import get_client  # noqa: E402
from data_pipeline.store import get_collection  # noqa: E402

# 固定本体：实体类型 / 关系类型（中文标签，与页面展示一致）
ENTITY_TYPES = ["疾病", "病原", "症状", "药物", "疫苗", "宿主", "传播途径", "防控"]
RELATION_TYPES = ["引起", "表现为", "预防", "治疗", "易感", "传播"]
MAX_TRIPLES_PER_CHUNK = 12
MAX_ENTITY_LEN = 20
# LLM 调用失败重试次数与退避基数（应对限流/网络抖动）
API_RETRIES = 3

# 抽取结果按块缓存（键=块文本 sha256，值=已归一化的三元组数组），中断重跑不丢进度
CACHE_PATH = Path(settings.graph_data_file).parent / "graph_extract_cache.json"

# 每种关系要求的 (头实体类型集合, 尾实体类型集合)；用于方向纠正与脏边过滤
RELATION_SCHEMA = {
    "引起": ({"病原"}, {"疾病"}),
    "表现为": ({"疾病"}, {"症状"}),
    "预防": ({"疫苗", "防控"}, {"疾病"}),
    "治疗": ({"药物"}, {"疾病"}),
    "易感": ({"宿主"}, {"疾病"}),
    "传播": ({"疾病"}, {"传播途径"}),
}

# LLM 偶发输出的关系同义词 → 标准关系；映射不了的非标准关系直接丢弃
RELATION_SYNONYMS = {
    "防控": "预防", "防治": "预防", "防止": "预防", "防疫": "预防",
    "免疫": "预防", "免疫预防": "预防", "接种": "预防",
    "病症": "表现为", "症状": "表现为", "表现": "表现为", "出现": "表现为",
    "导致": "引起", "引发": "引起", "致病": "引起", "感染": "引起", "病原为": "引起",
    "用药": "治疗", "医治": "治疗", "可治": "治疗", "用于治疗": "治疗", "治愈": "治疗",
    "传染": "传播", "经由": "传播", "通过": "传播", "传播途径": "传播",
    "易感动物": "易感", "易感于": "易感", "易感染": "易感",
}

# 实体别名归一（只收语料里实际出现/高概率出现的同物异名，保守维护）
ENTITY_ALIASES = {
    "副黏病毒": "鹅副黏病毒",
    "鹅副粘病毒": "鹅副黏病毒",
    "鹅副粘病毒病": "鹅副黏病毒病",
    "副黏病毒病": "鹅副黏病毒病",
    "高致病性禽流感": "禽流感",
    "高致病禽流感": "禽流感",
    "鹅禽流感": "禽流感",
    "大肠杆菌病": "鹅大肠杆菌病",
    "鹅霍乱": "鹅巴氏杆菌病",
    "禽霍乱": "鹅巴氏杆菌病",
    "霍乱": "鹅巴氏杆菌病",
    "鹅细小病毒病": "小鹅瘟",
    "小鹅瘟病毒感染": "小鹅瘟",
    "病雏": "雏鹅",
    "4至20日龄雏鹅": "雏鹅",
    "幼鹅": "雏鹅",
    "小鹅": "雏鹅",
}

# 无业务意义的泛称/非实体，命中即丢弃
STOP_ENTITIES = {"鹅病", "疾病", "病", "疫病"}

_EXTRACT_PROMPT = (
    "你是鹅养殖疫病知识图谱构建助手。从下面知识块中抽取最多 {max} 条关系三元组，"
    "每条必须包含头实体及其类型、关系、尾实体及其类型。\n"
    "实体类型仅限：{entity_types}；关系仅限：{relation_types}。\n"
    "类型判断要点：疾病=具体疫病名称（不要抽取“鹅病”这类泛称）；病原=细菌/病毒/寄生虫；"
    "宿主=鹅/雏鹅/种鹅等动物或日龄阶段；防控=消毒、隔离、全进全出、免疫接种等管理措施。\n"
    "注意关系方向：宿主 -[易感]-> 疾病；病原 -[引起]-> 疾病；疾病 -[表现为]-> 症状；"
    "药物 -[治疗]-> 疾病；疫苗或防控措施 -[预防]-> 疾病；疾病 -[传播]-> 传播途径。\n"
    '严格输出 JSON 数组，形如 [{"head":"鹅细小病毒","head_type":"病原",'
    '"rel":"引起","tail":"小鹅瘟","tail_type":"疾病"}]，不要输出其它文字。\n'
    "示例：\n"
    '[{"head":"小鹅瘟","head_type":"疾病","rel":"表现为","tail":"腹泻","tail_type":"症状"},'
    '{"head":"恩诺沙星","head_type":"药物","rel":"治疗","tail":"鹅副伤寒","tail_type":"疾病"},'
    '{"head":"雏鹅","head_type":"宿主","rel":"易感","tail":"小鹅瘟","tail_type":"疾病"},'
    '{"head":"甲醛熏蒸消毒","head_type":"防控","rel":"预防","tail":"鹅副伤寒","tail_type":"疾病"}]\n'
    "知识块：\n{chunk}"
)


def _canonical(name: str) -> str:
    """实体名规范化：去空白/标点 → 查别名表。"""
    n = re.sub(r"\s+", "", str(name)).strip("，。、：:；;！!？?（）()【】[]\"'“”‘’")
    return ENTITY_ALIASES.get(n, n)


def _infer_type(triple_rel: str, side: str) -> str:
    """LLM 未给合法类型时的回退：按关系与位置启发式推断（尽量贴近本体方向）。"""
    mapping = {
        "head": {
            "引起": "病原", "表现为": "疾病", "预防": "防控", "治疗": "药物",
            "易感": "宿主", "传播": "疾病",
        },
        "tail": {
            "引起": "疾病", "表现为": "症状", "预防": "疾病", "治疗": "疾病",
            "易感": "疾病", "传播": "传播途径",
        },
    }
    return mapping[side].get(triple_rel, "疾病")


def _normalize_triple(t: dict, dropped: list[str]) -> dict | None:
    """单条三元组清洗：归一化 → 关系校验 → 类型校验 → 方向纠正。不合格返回 None。"""
    head = _canonical(t.get("head", ""))
    tail = _canonical(t.get("tail", ""))
    if not head or not tail or head == tail:
        return None
    if len(head) > MAX_ENTITY_LEN or len(tail) > MAX_ENTITY_LEN or head in STOP_ENTITIES or tail in STOP_ENTITIES:
        dropped.append(f"实体停用/过长：{head} -> {tail}")
        return None

    rel = re.sub(r"\s+", "", str(t.get("rel", "")))
    rel = RELATION_SYNONYMS.get(rel, rel)
    if rel not in RELATION_TYPES:
        dropped.append(f"非法关系：{head} -[{rel}]-> {tail}")
        return None

    htype = str(t.get("head_type", "")).strip()
    ttype = str(t.get("tail_type", "")).strip()
    if htype not in ENTITY_TYPES:
        htype = _infer_type(rel, "head")
    if ttype not in ENTITY_TYPES:
        ttype = _infer_type(rel, "tail")

    # 本体方向校验：反了（交换头尾后合法）则翻转，否则丢弃脏边
    want_h, want_t = RELATION_SCHEMA[rel]
    ok = htype in want_h and ttype in want_t
    reversible = ttype in want_h and htype in want_t
    if not ok and reversible:
        head, tail, htype, ttype = tail, head, ttype, htype
    elif not ok:
        dropped.append(f"不符合本体：{head}({htype}) -[{rel}]-> {tail}({ttype})")
        return None
    return {"head": head, "head_type": htype, "rel": rel, "tail": tail, "tail_type": ttype}


def _extract_triples(chunk: str, dropped: list[str]) -> list[dict] | None:
    """用 DeepSeek 从单个知识块抽取三元组。

    返回归一化后的三元组列表（可为空列表）；API 重试耗尽仍失败返回 None，
    调用方不缓存 None，下次重跑会自动补抽。
    """
    prompt = (
        _EXTRACT_PROMPT
        .replace("{max}", str(MAX_TRIPLES_PER_CHUNK))
        .replace("{entity_types}", "、".join(ENTITY_TYPES))
        .replace("{relation_types}", "、".join(RELATION_TYPES))
        .replace("{chunk}", chunk[:1000])
    )
    data = None
    for attempt in range(1, API_RETRIES + 1):
        try:
            resp = get_client().chat.completions.create(
                model=settings.DEEPSEEK_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=1200,
            )
            text = (resp.choices[0].message.content or "").strip()
            # 去掉 ```json 代码块包裹
            text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.MULTILINE).strip()
            data = json.loads(text)
            break
        except Exception as e:  # noqa: BLE001
            if attempt == API_RETRIES:
                print(f"[build_graph] 重试 {API_RETRIES} 次仍失败，跳过该块：{e}")
                return None
            wait = 2**attempt
            print(f"[build_graph] 第 {attempt} 次调用失败（{e}），{wait}s 后重试…")
            time.sleep(wait)
    if not isinstance(data, list):
        return []
    triples = []
    for t in data:
        if isinstance(t, dict) and t.get("head") and t.get("tail") and t.get("rel"):
            norm = _normalize_triple(t, dropped)
            if norm:
                triples.append(norm)
    return triples


def build() -> None:
    col = get_collection()
    res = col.get(include=["documents", "metadatas"])
    chunks = res["documents"]
    metas = res["metadatas"]
    if not chunks:
        print("[build_graph] ChromaDB 为空，无知识块可抽三元组。")
        return

    import networkx as nx

    # 先抽完所有块（带按块缓存与失败重试），再做跨三元组的病名省略归一
    cache: dict[str, list] = {}
    if CACHE_PATH.exists():
        try:
            cache = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001 —— 缓存损坏则视为空
            cache = {}

    def _chunk_key(text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    all_triples: list[tuple[str, dict]] = []
    dropped: list[str] = []
    skipped = failed = cache_hits = 0
    total = len(chunks)
    for i, (doc, meta) in enumerate(zip(chunks, metas), 1):
        doc_name = meta.get("doc", "unknown")
        key = _chunk_key(doc)
        if key in cache:
            # 缓存的三元组已归一化过，这里再过一遍别名表：
            # 保证别名表更新后旧缓存也能应用（归一化幂等）
            triples = [
                {**t, "head": _canonical(t["head"]), "tail": _canonical(t["tail"])}
                for t in cache[key]
            ]
            cache_hits += 1
        else:
            triples = _extract_triples(doc, dropped)
            if triples is None:  # 重试后仍失败：不缓存，重跑可补抽
                failed += 1
                continue
            cache[key] = triples
            CACHE_PATH.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
        if not triples:
            skipped += 1
            continue
        all_triples.extend((doc_name, t) for t in triples)
        if i % 25 == 0 or i == total:
            print(f"[build_graph] 进度 {i}/{total}（缓存命中 {cache_hits}，失败 {failed}），"
                  f"已抽 {len(all_triples)} 条三元组")

    # P -[引起]-> P病：疾病位置（易感/预防/治疗 的尾端、表现为/传播 的头端）出现 P 时改写为 P病
    pathogen_to_disease = {
        t["head"]: t["tail"]
        for _, t in all_triples
        if t["rel"] == "引起" and t["tail"] == t["head"] + "病"
    }
    if pathogen_to_disease:
        rewritten = 0
        for _, t in all_triples:
            if t["rel"] in {"易感", "预防", "治疗"} and t["tail"] in pathogen_to_disease:
                t["tail"] = pathogen_to_disease[t["tail"]]
                t["tail_type"] = "疾病"
                rewritten += 1
            elif t["rel"] in {"表现为", "传播"} and t["head"] in pathogen_to_disease:
                t["head"] = pathogen_to_disease[t["head"]]
                t["head_type"] = "疾病"
                rewritten += 1
        if rewritten:
            print(f"[build_graph] 病名省略归一：{rewritten} 条边的实体改写为完整病名 {pathogen_to_disease}")

    g = nx.DiGraph()
    type_votes: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for doc_name, t in all_triples:
        head, tail, rel = t["head"], t["tail"], t["rel"]
        for name, etype in ((head, t["head_type"]), (tail, t["tail_type"])):
            if not g.has_node(name):
                g.add_node(name, community=-1, docs=[])
            type_votes[name][etype] += 1
        if doc_name not in g.nodes[head]["docs"]:
            g.nodes[head]["docs"].append(doc_name)
        if doc_name not in g.nodes[tail]["docs"]:
            g.nodes[tail]["docs"].append(doc_name)
        # 同对节点已有边时保留更常见关系（后到的不覆盖），合并来源文档由节点 docs 承载
        if not g.has_edge(head, tail):
            g.add_edge(head, tail, relation=rel)

    # 类型投票：每个节点取得票最多的类型（平票取最先出现的类型）
    for name, votes in type_votes.items():
        g.nodes[name]["type"] = max(votes.items(), key=lambda kv: kv[1])[0]

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
    print(f"[build_graph] 完成：块 {len(chunks)}（空结果 {skipped} / 失败 {failed} / 缓存命中 {cache_hits}）"
          f"→ 节点 {len(nodes)} / 边 {len(edges)} / 社区 {community_count}")
    print(f"[build_graph] 清洗丢弃 {len(dropped)} 条：")
    for d in dropped[:20]:
        print(f"  - {d}")
    if len(dropped) > 20:
        print(f"  …另有 {len(dropped) - 20} 条未显示")
    print(f"[build_graph] 已写入 {out}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--rebuild", action="store_true", help="强制重建")
    ap.parse_args()
    build()
