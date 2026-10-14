"""文档管理接口：上传入库 / 列表 / 分块预览 / 知识库检索 / 批量删除 / 本地知识库补录。

文档有两个来源，列表里统一展示：
- 上传：POST /documents/upload 存到 datasets/uploads/ 后入库
- 本地知识库：datasets/knowledge/ 下的离线语料（此前由 scripts/ingest.py 入库，没有 MySQL 记录）

向量库的文档键以「带后缀全名」为准，历史数据可能仍是去后缀 stem；
读取、删除、补录时两种键都会尝试，补录时统一迁移为带后缀全名。
"""
from datetime import datetime
from pathlib import Path

import anyio
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session as OrmSession

from core.topics import (
    FALLBACK_QUESTIONS,
    FALLBACK_TOPIC_ID,
    FALLBACK_TOPIC_LABEL,
    TOPICS,
    detect_topics,
)
from data_pipeline.embed import embed_texts
from data_pipeline.pipeline import (
    EmptyDocumentError,
    chunk_document,
    commit_document,
    prepare_document,
)
from data_pipeline.retriever import retrieve
from data_pipeline.store import (
    count as vector_count,
    delete_by_doc,
    get_chunks as vector_chunks,
    list_chunks,
    list_doc_chunks,
)
from db.models import Document
from db.session import get_db

router = APIRouter()

BASE_DIR = Path(__file__).resolve().parent.parent.parent
UPLOAD_DIR = BASE_DIR / "datasets" / "uploads"
KNOWLEDGE_DIR = BASE_DIR / "datasets" / "knowledge"
ALLOWED_SUFFIX = {".pdf", ".docx", ".txt", ".md"}

# 来源标签：按文件所在目录判断，无需额外建字段
SOURCE_UPLOAD = "upload"
SOURCE_KNOWLEDGE = "knowledge"
SOURCE_UNKNOWN = "unknown"


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int | None = None       # 离线入库的本地语料没有 MySQL 记录，此时为 None
    filename: str
    doc_key: str = ""           # 向量库中的文档键（ChromaDB metadata.doc）
    source: str = SOURCE_UNKNOWN
    file_type: str = ""
    chunk_count: int = 0        # MySQL 里记录的分块数
    indexed_chunks: int = 0     # 向量库里实际的块数
    status: str = "done"
    created_at: datetime | None = None
    replaced: bool = False      # 仅上传接口使用：True=本次替换了同名旧文档


class StatsOut(BaseModel):
    document_count: int         # 列表中的文档总数（含离线入库的语料）
    registered_count: int       # 有 MySQL 记录的数量
    vector_count: int           # 向量库实际块数
    pending_count: int          # 本地知识库中尚未入库的文件数
    latest_at: datetime | None
    upload_dir: str
    knowledge_dir: str


class ChunkOut(BaseModel):
    index: int
    text: str
    chars: int


class ChunkPageOut(BaseModel):
    name: str
    origin: str                 # vector=向量库 / file=本地文件现场分块 / empty=无可提取文本 / error=解析异常 / missing=找不到文件
    total: int
    offset: int
    limit: int
    chunks: list[ChunkOut]


class SearchRequest(BaseModel):
    query: str = Field(min_length=1)
    top_k: int = Field(default=5, ge=1, le=20)
    rerank: bool = True         # 走 bge-reranker 精排，更准但稍慢


class HitOut(BaseModel):
    doc: str
    index: int
    text: str
    chars: int
    rerank_score: float | None = None
    distance: float | None = None


class SearchOut(BaseModel):
    query: str
    count: int
    hits: list[HitOut]


class DeleteRequest(BaseModel):
    ids: list[int] = []         # 按 MySQL id 删除
    names: list[str] = []       # 按向量库文档键 / 文件名删除（离线入库的文档用这个）


class DeleteResultOut(BaseModel):
    deleted: int
    details: list[str]


class LibraryItemOut(BaseModel):
    filename: str
    size: int
    modified_at: datetime
    indexed_chunks: int
    status: str                 # indexed=已在库 / missing=未入库


class LibraryOut(BaseModel):
    dir: str
    items: list[LibraryItemOut]


class LibrarySyncRequest(BaseModel):
    names: list[str] = []       # 为空表示补录全部
    force: bool = False         # 默认跳过块数一致的文档，避免重复向量化


class LibrarySyncResultOut(BaseModel):
    filename: str
    action: str                 # created / updated / skipped / failed
    chunk_count: int = 0
    message: str = ""


class TopicCoverageOut(BaseModel):
    id: str
    label: str
    chunk_count: int            # 该维度命中的知识块数
    doc_count: int              # 覆盖到的语料份数
    docs: list[str] = []
    questions: list[str] = []   # 该维度的快捷提问模板（前端「去检索」直接复用）
    thin: bool = False          # 语料偏薄，建议补充


# 维度知识块低于该数量视为覆盖偏薄
THIN_CHUNK_THRESHOLD = 10


def _candidate_keys(filename: str) -> list[str]:
    """向量库文档键候选：新数据是带后缀全名，历史数据是去后缀 stem。"""
    stem = Path(filename).stem
    return [filename] if stem == filename else [filename, stem]


def _is_inside(path: Path, folder: Path) -> bool:
    try:
        path.resolve().relative_to(folder.resolve())
        return True
    except (OSError, ValueError):
        return False


def _source_of(file_path: str | Path | None) -> str:
    """按文件位置判断来源：datasets/uploads=上传，datasets/knowledge=本地知识库。"""
    if not file_path:
        return SOURCE_UNKNOWN
    path = Path(file_path)
    if _is_inside(path, UPLOAD_DIR):
        return SOURCE_UPLOAD
    if _is_inside(path, KNOWLEDGE_DIR):
        return SOURCE_KNOWLEDGE
    return SOURCE_UNKNOWN


def _find_local_file(name: str) -> Path | None:
    """按文档键在本地知识库 / 上传目录定位文件（兼容带后缀全名与去后缀 stem）。"""
    stem = Path(name).stem
    for folder in (KNOWLEDGE_DIR, UPLOAD_DIR):
        if not folder.is_dir():
            continue
        for path in folder.iterdir():
            if not path.is_file():
                continue
            if path.name == name or (
                path.stem == stem and path.suffix.lower() in ALLOWED_SUFFIX
            ):
                return path
    return None


def _merge_documents(db: OrmSession) -> list[DocumentOut]:
    """MySQL 元数据与向量库实际块数合并；向量库里「有块无记录」的文档也会列出。"""
    rows = db.scalars(select(Document).order_by(Document.created_at.desc())).all()
    vector_map = list_doc_chunks()
    claimed: set[str] = set()
    items: list[DocumentOut] = []

    for row in rows:
        doc_key, indexed = row.filename, 0
        for key in _candidate_keys(row.filename):
            if vector_map.get(key, 0) > 0:
                doc_key, indexed = key, vector_map[key]
                break
        claimed.update(key for key in _candidate_keys(row.filename) if key in vector_map)
        items.append(
            DocumentOut(
                id=row.id,
                filename=row.filename,
                doc_key=doc_key,
                source=_source_of(row.file_path),
                file_type=row.file_type,
                chunk_count=row.chunk_count,
                indexed_chunks=indexed,
                status=row.status,
                created_at=row.created_at,
            )
        )

    for key, chunks in sorted(vector_map.items(), key=lambda kv: -kv[1]):
        if key in claimed:
            continue
        local = _find_local_file(key)
        items.append(
            DocumentOut(
                id=None,
                filename=key,
                doc_key=key,
                source=_source_of(local) if local else SOURCE_UNKNOWN,
                file_type=local.suffix.lstrip(".").lower() if local else "",
                chunk_count=chunks,
                indexed_chunks=chunks,
                status="done",
                created_at=datetime.fromtimestamp(local.stat().st_mtime) if local else None,
            )
        )
    return items


def _library_items() -> list[LibraryItemOut]:
    """扫描 datasets/knowledge/，对照向量库给出每个文件的入库状态。"""
    if not KNOWLEDGE_DIR.is_dir():
        return []
    vector_map = list_doc_chunks()
    items: list[LibraryItemOut] = []
    for path in sorted(KNOWLEDGE_DIR.iterdir(), key=lambda p: p.name):
        if not path.is_file() or path.suffix.lower() not in ALLOWED_SUFFIX:
            continue
        stat = path.stat()
        indexed = max(vector_map.get(key, 0) for key in _candidate_keys(path.name))
        items.append(
            LibraryItemOut(
                filename=path.name,
                size=stat.st_size,
                modified_at=datetime.fromtimestamp(stat.st_mtime),
                indexed_chunks=indexed,
                status="indexed" if indexed else "missing",
            )
        )
    return items


def _delete_vectors_by_name(name: str, vector_map: dict[str, int] | None = None) -> int:
    """按文档键删除向量（带后缀全名与历史去后缀键都尝试），返回删除块数。"""
    vector_map = vector_map if vector_map is not None else list_doc_chunks()
    removed = 0
    for key in _candidate_keys(name):
        if vector_map.get(key, 0):
            removed += delete_by_doc(key)
            vector_map.pop(key, None)
    return removed


def _delete_document(db: OrmSession, doc: Document) -> str:
    """删除单个文档：向量块 + 本地文件 + MySQL 记录。"""
    removed = _delete_vectors_by_name(doc.filename)
    uploaded = Path(doc.file_path) if doc.file_path else None
    if uploaded and uploaded.exists():
        uploaded.unlink(missing_ok=True)
    db.delete(doc)
    db.commit()
    return f"{doc.filename}（{removed} 块）"


@router.post("/documents/upload", response_model=DocumentOut)
async def upload_document(file: UploadFile = File(...), db: OrmSession = Depends(get_db)):
    """上传文档：自动解析分块入库，元数据写入 MySQL。同名文件按「替换」处理。"""
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

        # 阶段 2：解析成功后才替换旧数据。向量库 doc 键统一用「带后缀全名」，
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
        return DocumentOut(
            id=doc.id,
            filename=doc.filename,
            doc_key=filename,
            source=SOURCE_UPLOAD,
            file_type=doc.file_type,
            chunk_count=doc.chunk_count,
            indexed_chunks=len(prepared["chunks"]),
            status=doc.status,
            created_at=doc.created_at,
            replaced=replaced,
        )
    finally:
        # 成功时临时文件已 rename；失败时清理，避免孤儿文件
        tmp.unlink(missing_ok=True)


@router.get("/documents", response_model=list[DocumentOut])
async def list_documents(db: OrmSession = Depends(get_db)):
    """文档列表（最新在前）：MySQL 元数据与向量库实际块数合并，上传与本地语料统一展示。"""
    return _merge_documents(db)


@router.get("/documents/stats", response_model=StatsOut)
async def document_stats(db: OrmSession = Depends(get_db)):
    """知识库概览：文档数、向量块数、本地待补录数、最近入库时间。"""
    items = _merge_documents(db)
    library = _library_items()
    return StatsOut(
        document_count=len(items),
        registered_count=sum(1 for item in items if item.id is not None),
        vector_count=vector_count(),
        pending_count=sum(1 for item in library if item.status == "missing"),
        latest_at=max((item.created_at for item in items if item.created_at), default=None),
        upload_dir=str(UPLOAD_DIR),
        knowledge_dir=str(KNOWLEDGE_DIR),
    )


def _topic_coverage() -> list[TopicCoverageOut]:
    """统计各提问维度被多少知识块与语料覆盖。

    每个块只计入得分最高的那个维度（detect_topics 返回的首项），
    口径统一、同一块不会被重复计数。
    """
    buckets: dict[str, dict] = {topic.id: {"chunks": 0, "docs": set()} for topic in TOPICS}
    buckets[FALLBACK_TOPIC_ID] = {"chunks": 0, "docs": set()}

    for doc_key, text in list_chunks():
        primary = detect_topics(text)[0]
        bucket = buckets.get(primary)
        if bucket is None:
            continue
        bucket["chunks"] += 1
        bucket["docs"].add(doc_key)

    items = [
        TopicCoverageOut(
            id=topic.id,
            label=topic.label,
            chunk_count=buckets[topic.id]["chunks"],
            doc_count=len(buckets[topic.id]["docs"]),
            docs=sorted(buckets[topic.id]["docs"]),
            questions=list(topic.questions),
            thin=buckets[topic.id]["chunks"] < THIN_CHUNK_THRESHOLD,
        )
        for topic in TOPICS
    ]
    items.append(
        TopicCoverageOut(
            id=FALLBACK_TOPIC_ID,
            label=FALLBACK_TOPIC_LABEL,
            chunk_count=buckets[FALLBACK_TOPIC_ID]["chunks"],
            doc_count=len(buckets[FALLBACK_TOPIC_ID]["docs"]),
            docs=sorted(buckets[FALLBACK_TOPIC_ID]["docs"]),
            questions=list(FALLBACK_QUESTIONS),
        )
    )
    return items


@router.get("/documents/topics", response_model=list[TopicCoverageOut])
async def document_topic_coverage():
    """知识库维度覆盖度：每个提问维度有多少知识块与语料，用来发现储备短板。"""
    return await anyio.to_thread.run_sync(_topic_coverage)


@router.get("/documents/chunks", response_model=ChunkPageOut)
async def document_chunks(
    name: str = Query(..., description="文档名或向量库文档键"),
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=200),
    keyword: str = Query("", description="按关键字过滤分块内容"),
):
    """分块预览：优先读向量库；未入库的本地文件回退到现场解析分块。"""

    def load() -> tuple[list[dict], str]:
        for key in _candidate_keys(name):
            rows = vector_chunks(key, keyword)
            if rows:
                return rows, "vector"
        local = _find_local_file(name)
        if local is None:
            return [], "missing"
        # 扫描版 PDF 没有文字层、或文件损坏时，这里不应把 500 抛给前端
        try:
            chunks = chunk_document(local)["chunks"]
        except EmptyDocumentError:
            return [], "empty"
        except Exception:  # noqa: BLE001
            return [], "error"
        rows = [
            {"index": index, "text": text, "chars": len(text)}
            for index, text in enumerate(chunks)
        ]
        if keyword:
            rows = [row for row in rows if keyword in row["text"]]
        return rows, "file"

    rows, origin = await anyio.to_thread.run_sync(load)
    return ChunkPageOut(
        name=name,
        origin=origin,
        total=len(rows),
        offset=offset,
        limit=limit,
        chunks=[ChunkOut(**row) for row in rows[offset : offset + limit]],
    )


@router.post("/documents/search", response_model=SearchOut)
async def search_documents(req: SearchRequest):
    """知识库语义检索：直接给出命中的知识块与来源文档，用于核对「知识库里到底有什么」。"""
    try:
        hits = await anyio.to_thread.run_sync(
            lambda: retrieve(req.query, top_k=req.top_k, rerank=req.rerank)
        )
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"检索失败：{e}") from e
    return SearchOut(
        query=req.query,
        count=len(hits),
        hits=[
            HitOut(
                doc=str(hit["metadata"].get("doc", "")),
                index=int(hit["metadata"].get("index", 0)),
                text=hit["document"],
                chars=len(hit["document"]),
                rerank_score=hit.get("rerank_score"),
                distance=(
                    round(float(hit["distance"]), 4)
                    if hit.get("distance") is not None
                    else None
                ),
            )
            for hit in hits
        ],
    )


@router.post("/documents/delete", response_model=DeleteResultOut)
async def delete_documents(req: DeleteRequest, db: OrmSession = Depends(get_db)):
    """批量删除：ids 按 MySQL 记录删除，names 用于离线入库（没有记录）的文档。"""
    details: list[str] = []
    vector_map = list_doc_chunks()

    for doc_id in req.ids:
        doc = db.get(Document, doc_id)
        if doc is None:
            continue
        details.append(_delete_document(db, doc))

    for name in req.names:
        removed = _delete_vectors_by_name(name, vector_map)
        local = _find_local_file(name)
        if local is not None:
            local.unlink(missing_ok=True)
        row = db.scalars(select(Document).where(Document.filename == name)).first()
        if row is not None:
            db.delete(row)
            db.commit()
        details.append(f"{name}（{removed} 块）")

    return DeleteResultOut(deleted=len(details), details=details)


@router.delete("/documents/{doc_id}")
async def delete_document(doc_id: int, db: OrmSession = Depends(get_db)):
    """按 id 删除文档：MySQL 元数据 + ChromaDB 向量块 + 本地文件。"""
    doc = db.get(Document, doc_id)
    if doc is None:
        raise HTTPException(status_code=404, detail=f"文档 {doc_id} 不存在")
    return {"deleted": doc_id, "detail": _delete_document(db, doc)}


@router.get("/documents/library", response_model=LibraryOut)
async def list_library():
    """本地知识库语料清单（datasets/knowledge/）及其入库状态。"""
    return LibraryOut(dir=str(KNOWLEDGE_DIR), items=_library_items())


@router.post("/documents/library/sync", response_model=list[LibrarySyncResultOut])
async def sync_library(req: LibrarySyncRequest, db: OrmSession = Depends(get_db)):
    """把 datasets/knowledge/ 下的语料补录入库，并同步 MySQL 元数据。

    默认跳过「向量库块数与当前解析块数一致」的文件（重新向量化很贵），
    force=True 时强制重嵌入；无论是否重嵌入都会补上 MySQL 记录，
    这样文档列表才能反映真实的知识库规模。
    """
    if not KNOWLEDGE_DIR.is_dir():
        raise HTTPException(status_code=404, detail=f"知识库目录不存在：{KNOWLEDGE_DIR}")

    wanted = set(req.names)
    targets = [
        path
        for path in sorted(KNOWLEDGE_DIR.iterdir(), key=lambda p: p.name)
        if path.is_file()
        and path.suffix.lower() in ALLOWED_SUFFIX
        and (not wanted or path.name in wanted)
    ]
    if not targets:
        raise HTTPException(status_code=400, detail="没有匹配的本地知识文件")

    vector_map = list_doc_chunks()
    results: list[LibrarySyncResultOut] = []

    for path in targets:
        try:
            prepared = await anyio.to_thread.run_sync(chunk_document, path)
        except EmptyDocumentError as e:
            results.append(LibrarySyncResultOut(filename=path.name, action="failed", message=str(e)))
            continue
        except Exception as e:  # noqa: BLE001
            results.append(
                LibrarySyncResultOut(filename=path.name, action="failed", message=f"解析失败：{e}")
            )
            continue

        chunks = prepared["chunks"]
        keys = _candidate_keys(path.name)
        existing = max(vector_map.get(key, 0) for key in keys)
        action = "updated" if existing else "created"
        message = f"{prepared['chars']} 字符 → {len(chunks)} 块"

        if existing == len(chunks) and not req.force:
            action = "skipped"
            message = "块数与库中一致，跳过重新向量化"
        else:
            try:
                _delete_vectors_by_name(path.name, vector_map)
                embeddings = await anyio.to_thread.run_sync(embed_texts, chunks)
                await anyio.to_thread.run_sync(
                    commit_document,
                    path.name,
                    {"chunks": chunks, "embeddings": embeddings},
                )
                vector_map[path.name] = len(chunks)
            except Exception as e:  # noqa: BLE001
                results.append(
                    LibrarySyncResultOut(filename=path.name, action="failed", message=f"入库失败：{e}")
                )
                continue

        row = db.scalars(select(Document).where(Document.filename == path.name)).first()
        doc = row or Document(filename=path.name)
        if row is None:
            db.add(doc)
        doc.file_path = str(path)
        doc.file_type = path.suffix.lstrip(".").lower()
        doc.chunk_count = len(chunks)
        doc.status = "done"
        db.commit()

        results.append(
            LibrarySyncResultOut(
                filename=path.name,
                action=action,
                chunk_count=len(chunks),
                message=message,
            )
        )
    return results
