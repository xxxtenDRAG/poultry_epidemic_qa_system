"""文档管理接口：上传（解析→分块→向量化→ChromaDB + 元数据入 MySQL）/ 列表 / 删除。"""
from datetime import datetime
from pathlib import Path

import anyio
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session as OrmSession

from data_pipeline.pipeline import EmptyDocumentError, commit_document, prepare_document
from data_pipeline.store import delete_by_doc
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
    replaced: bool = False  # True=本次上传替换了同名旧文档


@router.post("/documents/upload", response_model=DocumentOut)
async def upload_document(file: UploadFile = File(...), db: OrmSession = Depends(get_db)):
    """上传文档：自动解析分块入库，元数据写入 MySQL。同名文件按“替换”处理。"""
    filename = Path(file.filename or "unnamed").name
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_SUFFIX:
        raise HTTPException(status_code=400, detail=f"不支持格式 {suffix}，仅支持 {sorted(ALLOWED_SUFFIX)}")

    # 先存到临时文件（保留原后缀以便解析器识别类型），解析成功后才覆盖正式文件，
    # 避免坏文件覆盖旧文件、或解析失败却已删掉旧向量。
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    target = UPLOAD_DIR / filename
    tmp = target.with_name(f"{target.stem}.uploading{suffix}")
    tmp.write_bytes(await file.read())

    try:
        # 阶段 1：解析 → 分块 → 向量化（不写库、不动旧数据）
        try:
            prepared = await anyio.to_thread.run_sync(prepare_document, tmp)
        except EmptyDocumentError as e:
            raise HTTPException(status_code=422, detail=str(e)) from e
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"文档解析入库失败：{e}") from e

        # 阶段 2：解析成功后才替换旧数据。向量库 doc 键统一用“带后缀全名”，
        # 历史数据（离线入库/旧版接口）用的是去后缀 stem，两种键都清一次。
        stem = Path(filename).stem
        await anyio.to_thread.run_sync(delete_by_doc, filename)
        if stem != filename:
            await anyio.to_thread.run_sync(delete_by_doc, stem)
        await anyio.to_thread.run_sync(commit_document, filename, prepared)

        # 阶段 3：临时文件原子覆盖正式文件（Windows 上 os.replace 可覆盖已存在文件）
        tmp.replace(target)

        # 元数据入 MySQL：同名行更新而非新增（避免列表出现重复记录）
        existed = db.scalars(select(Document).where(Document.filename == filename)).first()
        replaced = existed is not None
        doc = existed or Document(filename=filename)
        if existed is None:
            db.add(doc)
        doc.file_path = str(target)
        doc.file_type = suffix.lstrip(".")
        doc.chunk_count = len(prepared["chunks"])
        doc.status = "done"
        doc.created_at = datetime.now()
        db.commit()
        db.refresh(doc)
        out = DocumentOut.model_validate(doc)
        out.replaced = replaced
        return out
    finally:
        # 成功时临时文件已 rename；失败时清理，避免孤儿文件
        tmp.unlink(missing_ok=True)


@router.get("/documents", response_model=list[DocumentOut])
async def list_documents(db: OrmSession = Depends(get_db)):
    """文档列表（最新在前）。"""
    return db.scalars(select(Document).order_by(Document.created_at.desc())).all()


@router.delete("/documents/{doc_id}")
async def delete_document(doc_id: int, db: OrmSession = Depends(get_db)):
    """删除文档：MySQL 元数据 + ChromaDB 向量块 + 本地文件。"""
    doc = db.get(Document, doc_id)
    if doc is None:
        raise HTTPException(status_code=404, detail=f"文档 {doc_id} 不存在")
    # 先删向量库与本地文件，再删元数据。
    # 向量库 doc 键可能是带后缀全名（新数据）或去后缀 stem（历史数据），两种都尝试。
    delete_by_doc(doc.filename)
    stem = Path(doc.filename).stem
    if stem != doc.filename:
        delete_by_doc(stem)
    uploaded = Path(doc.file_path)
    if uploaded.exists():
        uploaded.unlink(missing_ok=True)
    db.delete(doc)
    db.commit()
    return {"deleted": doc_id}
