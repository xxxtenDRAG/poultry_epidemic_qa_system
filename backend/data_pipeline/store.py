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
    """将分块文本 + 向量入库，id 形如 {doc_name}-{i}。"""
    col = get_collection()
    ids = [f"{doc_name}-{i}" for i in range(len(chunks))]
    metadatas = [{"doc": doc_name, "index": i} for i in range(len(chunks))]
    col.add(ids=ids, documents=chunks, embeddings=embeddings, metadatas=metadatas)


def search(query_embedding: list[float], top_k: int | None = None) -> list[dict]:
    """向量检索，返回 Top-K 结果 [{id, document, metadata, distance}]。"""
    col = get_collection()
    top_k = top_k or settings.TOP_K
    res = col.query(query_embeddings=[query_embedding], n_results=top_k, include=["documents", "metadatas", "distances"])
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
    return results


def count() -> int:
    return get_collection().count()
