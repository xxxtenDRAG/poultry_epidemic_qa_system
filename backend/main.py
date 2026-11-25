"""FastAPI 应用入口。

启动：uvicorn main:app --reload --port 8000
接口文档：http://localhost:8000/docs
"""
import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

import anyio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from core.config import settings
from core.exceptions import register_exception_handlers
from api import chat, documents, graph, sessions, traceability
from db.init_db import init_db
from db.seed_traceability import seed_traceability

BASE_DIR = Path(__file__).resolve().parent.parent


def _warmup_embedder() -> None:
    """预加载 bge 向量模型，避免首次提问时现场加载（约 2-5s）。"""
    from data_pipeline.embed import embed_texts

    embed_texts(["预热"])


def _warmup_reranker() -> None:
    """预加载 bge-reranker 精排模型（约 1.1GB，后台加载）。"""
    from data_pipeline.rerank import get_reranker

    get_reranker()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """启动时自动建库建表、写入演示溯源数据，并后台预热向量模型与精排模型。"""
    init_db()
    seed_traceability()
    loop = asyncio.get_running_loop()
    loop.create_task(anyio.to_thread.run_sync(_warmup_embedder))
    loop.create_task(anyio.to_thread.run_sync(_warmup_reranker))
    yield


app = FastAPI(
    title=settings.PROJECT_NAME,
    version="0.1.0",
    description="鹅养殖疫病风险评估交互式问答系统 API",
    lifespan=lifespan,
)

# 开发环境跨域：允许前端本地调试
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 统一异常处理
register_exception_handlers(app)

# 注册路由
app.include_router(chat.router, prefix="/api", tags=["chat"])
app.include_router(documents.router, prefix="/api", tags=["documents"])
app.include_router(graph.router, prefix="/api", tags=["graph"])
app.include_router(sessions.router, prefix="/api", tags=["sessions"])
app.include_router(traceability.router, prefix="/api", tags=["traceability"])

# 挂载上传图片静态目录
_uploads_dir = BASE_DIR / "data" / "uploads"
_uploads_dir.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(_uploads_dir)), name="uploads")


@app.get("/api/health", tags=["system"])
async def health_check():
    """健康检查。"""
    return {"status": "ok", "project": settings.PROJECT_NAME, "version": "0.1.0"}
