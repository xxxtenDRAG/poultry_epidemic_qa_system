"""FastAPI 应用入口。

启动：uvicorn main:app --reload --port 8000
接口文档：http://localhost:8000/docs
"""
import asyncio
from contextlib import asynccontextmanager

import anyio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.config import settings
from api import chat, documents, graph, sessions
from db.init_db import init_db


def _warmup_embedder() -> None:
    """预加载 bge 向量模型，避免首次提问时现场加载（约 2-5s）。"""
    from data_pipeline.embed import embed_texts

    embed_texts(["预热"])


@asynccontextmanager
async def lifespan(app: FastAPI):
    """启动时自动建库建表，并后台预热向量模型。"""
    init_db()
    asyncio.get_running_loop().create_task(anyio.to_thread.run_sync(_warmup_embedder))
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

# 注册路由
app.include_router(chat.router, prefix="/api", tags=["chat"])
app.include_router(documents.router, prefix="/api", tags=["documents"])
app.include_router(graph.router, prefix="/api", tags=["graph"])
app.include_router(sessions.router, prefix="/api", tags=["sessions"])


@app.get("/api/health", tags=["system"])
async def health_check():
    """健康检查。"""
    return {"status": "ok", "project": settings.PROJECT_NAME, "version": "0.1.0"}
