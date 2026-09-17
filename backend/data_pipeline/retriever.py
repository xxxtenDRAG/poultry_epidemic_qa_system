"""统一检索模块：向量召回 +（可选）bge-reranker 精排。

被 Agent、脚本、接口共用，避免各处重复实现。
"""
from data_pipeline.embed import embed_texts
from data_pipeline.store import search as vector_search


def retrieve(query: str, top_k: int | None = None, rerank: bool = True) -> list[dict]:
    """单 Query 检索：embed → 向量召回 → 精排取 Top-K。"""
    emb = embed_texts([query])[0]
    return vector_search(emb, top_k=top_k, query=query, rerank=rerank)


def retrieve_multi(
    queries: list[str], top_k: int | None = None, rerank: bool = True
) -> list[dict]:
    """多 Query 召回：逐条检索后按 (文档, 块号) 去重，合并取 Top-K。"""
    results: list[dict] = []
    for q in queries:
        results.extend(retrieve(q, top_k=top_k, rerank=rerank))
    seen: set = set()
    dedup: list[dict] = []
    for r in results:
        key = (r["metadata"]["doc"], r["metadata"]["index"])
        if key not in seen:
            seen.add(key)
            dedup.append(r)
    return dedup[: top_k or 5]
