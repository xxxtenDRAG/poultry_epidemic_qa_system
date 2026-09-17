"""文档管理接口：上传（解析→分块→向量化→ChromaDB + 元数据入 MySQL）/ 列表 / 删除。"""
from datetime import datetime
from pathlib import Path

import anyio
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session as OrmSession

from data_pipeline.pipeline import process_document
from db.models import Document
from db.session import get_db

router = APIRouter()

UPLOAD_DIR = Path(__file__).resolve().parent.parent.parent / "datasets" / "uploads"
ALLOWED_SUFFIX = {".pdf", ".docx", ".txt", ".md"}


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    filename: str
    file_type: str
    chunk_count: int
    status: str
    created_at: datetime


@router.post("/documents/upload", response_model=DocumentOut)
async def upload_document(file: UploadFile = File(...), db: OrmSession = Depends(get_db)):
    """上传文档：自动解析分块入库，元数据写入 MySQL。"""
    filename = Path(file.filename or "unnamed").name
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_SUFFIX:
        raise HTTPException(status_code=400, detail=f"不支持格式 {suffix}，仅支持 {sorted(ALLOWED_SUFFIX)}")

    # 保存文件
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    target = UPLOAD_DIR / filename
    target.write_bytes(await file.read())

    # 流水线处理（阻塞，放线程池）
    try:
        result = await anyio.to_thread.run_sync(process_document, target, Path(filename).stem)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"文档解析入库失败：{e}") from e

    # 元数据入 MySQL
    doc = Document(
        filename=filename,
        file_path=str(target),
        file_type=suffix.lstrip("."),
        chunk_count=result["chunk_count"],
        status="done",
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc


@router.get("/documents", response_model=list[DocumentOut])
async def list_documents(db: OrmSession = Depends(get_db)):
    """文档列表（最新在前）。"""
    return db.scalars(select(Document).order_by(Document.created_at.desc())).all()


@router.delete("/documents/{doc_id}")
async def delete_document(doc_id: int, db: OrmSession = Depends(get_db)):
    """删除文档元数据（ChromaDB 向量删除为阶段 3 增强项）。"""
    doc = db.get(Document, doc_id)
    if doc is None:
        raise HTTPException(status_code=404, detail=f"文档 {doc_id} 不存在")
    db.delete(doc)
    db.commit()
    return {"deleted": doc_id}
