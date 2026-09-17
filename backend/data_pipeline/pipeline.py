"""文档处理流水线入口：解析 → 分块 → bge 向量化 → ChromaDB 入库。

供 API 上传接口（api/documents.py）与离线脚本（scripts/ingest.py）复用。
"""
from pathlib import Path

from data_pipeline.chunk import chunk_text
from data_pipeline.embed import embed_texts
from data_pipeline.parse import parse_document
from data_pipeline.store import add_documents


def process_document(file_path: str | Path, doc_name: str | None = None) -> dict:
    """处理单个文档，返回 {"doc_name", "chars", "chunk_count"}。"""
    file_path = Path(file_path)
    name = doc_name or file_path.stem

    text = parse_document(file_path)
    chunks = chunk_text(text)
    embeddings = embed_texts(chunks)
    add_documents(name, chunks, embeddings)
    return {"doc_name": name, "chars": len(text), "chunk_count": len(chunks)}
