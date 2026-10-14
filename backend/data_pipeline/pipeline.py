"""文档处理流水线入口：解析 → 分块 → bge 向量化 → ChromaDB 入库。

供 API 上传接口（api/documents.py）与离线脚本（scripts/ingest.py）复用。
拆成 prepare（解析/分块/向量化，不写库）与 commit（写库）两阶段，
保证新文档解析失败时不会破坏任何已有数据。
"""
from pathlib import Path

from data_pipeline.chunk import chunk_text
from data_pipeline.embed import embed_texts
from data_pipeline.parse import parse_document
from data_pipeline.store import add_documents


class EmptyDocumentError(ValueError):
    """解析后无可用文本（扫描版/图片版 PDF、空文档等）。"""


def prepare_document(file_path: str | Path) -> dict:
    """解析 → 分块 → 向量化，返回 {chars, chunks, embeddings}，不写向量库。"""
    prepared = chunk_document(file_path)
    prepared["embeddings"] = embed_texts(prepared["chunks"])
    return prepared


def chunk_document(file_path: str | Path) -> dict:
    """解析 → 分块，返回 {chars, chunks}，不做向量化。

    供「本地知识库补录」先比对块数：块数与库中一致就跳过重新 embedding，
    500+ 块的大文档能省下几十秒 CPU。
    """
    file_path = Path(file_path)
    suffix = file_path.suffix.lower()

    text = parse_document(file_path)
    if not text or not text.strip():
        if suffix == ".pdf":
            raise EmptyDocumentError(
                "未从该 PDF 提取到任何文本：它可能是扫描件或图片版 PDF，"
                "请先进行 OCR 文字识别，或改传带文字层的 PDF / DOCX / TXT / MD 文件"
            )
        raise EmptyDocumentError("文档内容为空，未生成任何知识块")

    chunks = chunk_text(text)
    if not chunks:
        raise EmptyDocumentError("文档分块结果为空，请检查文档内容")

    return {"chars": len(text), "chunks": chunks}


def commit_document(doc_name: str, prepared: dict) -> None:
    """将 prepare 阶段的结果写入向量库。"""
    add_documents(doc_name, prepared["chunks"], prepared["embeddings"])


def process_document(file_path: str | Path, doc_name: str | None = None) -> dict:
    """处理单个文档（离线脚本用，全流程一次完成），返回 {"doc_name", "chars", "chunk_count"}。"""
    name = doc_name or Path(file_path).stem
    prepared = prepare_document(file_path)
    commit_document(name, prepared)
    return {
        "doc_name": name,
        "chars": prepared["chars"],
        "chunk_count": len(prepared["chunks"]),
    }
