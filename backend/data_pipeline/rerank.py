"""bge-reranker-base 精排模块（本地 CrossEncoder，无需 API Key）。

作用：向量召回 Top-20 后，用交叉编码器对 (query, chunk) 逐一打分重排，
只保留最终 Top-K，提升命中精度。
"""
from functools import lru_cache

from core.config import settings


@lru_cache(maxsize=1)
def get_reranker():
    """首次调用会从 HuggingFace 下载 bge-reranker-base（约 1.1GB）。"""
    from sentence_transformers import CrossEncoder

    return CrossEncoder(settings.RERANK_MODEL, max_length=512)


def rerank(query: str, candidates: list[dict]) -> list[dict]:
    """对候选块按 (query, chunk) 相关性重排，原地补充 rerank_score 字段。"""
    if len(candidates) <= 1:
        return candidates
    pairs = [(query, c["document"]) for c in candidates]
    scores = get_reranker().predict(pairs)
    for c, s in zip(candidates, scores):
        c["rerank_score"] = float(s)
    return sorted(candidates, key=lambda c: c["rerank_score"], reverse=True)
