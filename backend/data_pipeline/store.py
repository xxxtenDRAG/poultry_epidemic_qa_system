"""ChromaDB 向量库：集合管理、入库、相似度检索。"""
from functools import lru_cache
from pathlib import Path

import chromadb

from core.config import settings

COLLECTION_NAME = "goose_knowledge"


@lru_cache(maxsize=1)
def get_collection():
    persist_dir = Path(settings.CHROMA_PERSIST_DIR)
    persist_dir.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(persist_dir))
    return client.get_or_create_collection(COLLECTION_NAME)


def add_documents(
    doc_name: str,
    chunks: list[str],
    embeddings: list[list[float]],
) -> None:
    """将分块文本 + 向量入库（upsert，幂等），id 形如 {doc_name}-{i}。

    用 upsert 而非 add：同名文档替换时重复 ID 不会报错；
    注意块数变少的场景需调用方先 delete_by_doc 清旧块。
    """
    col = get_collection()
    if not chunks or not embeddings:
        raise ValueError("没有可入库的文本块或向量（文档可能解析为空，如扫描版 PDF）")
    ids = [f"{doc_name}-{i}" for i in range(len(chunks))]
    metadatas = [{"doc": doc_name, "index": i} for i in range(len(chunks))]
    col.upsert(ids=ids, documents=chunks, embeddings=embeddings, metadatas=metadatas)


def search(
    query_embedding: list[float],
    top_k: int | None = None,
    query: str | None = None,
    rerank: bool = False,
    rerank_pool: int = 20,
) -> list[dict]:
    """向量检索，返回 Top-K 结果 [{id, document, metadata, distance}]。

    rerank=True 时先用更大池子（rerank_pool）召回，再用 bge-reranker 精排取 Top-K。
    """
    col = get_collection()
    top_k = top_k or settings.TOP_K
    n_results = max(top_k, rerank_pool) if rerank else top_k
    res = col.query(
        query_embeddings=[query_embedding],
        n_results=n_results,
        include=["documents", "metadatas", "distances"],
    )
    results: list[dict] = []
    for i, doc_id in enumerate(res["ids"][0]):
        results.append(
            {
                "id": doc_id,
                "document": res["documents"][0][i],
                "metadata": res["metadatas"][0][i],
                "distance": res["distances"][0][i],
            }
        )
    if rerank and query:
        from data_pipeline.rerank import rerank as _rerank

        results = _rerank(query, results)[:top_k]
    return results


def count() -> int:
    return get_collection().count()


def delete_by_doc(doc_name: str) -> int:
    """删除指定文档的全部向量块，返回删除数量。"""
    col = get_collection()
    res = col.get(where={"doc": doc_name}, include=[])
    ids = res["ids"]
    if ids:
        col.delete(ids=ids)
    return len(ids)
