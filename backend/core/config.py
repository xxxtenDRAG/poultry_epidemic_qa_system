"""全局配置：从环境变量 / .env 读取，密钥严禁硬编码。"""
import os
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# 项目根目录（backend/ 的上两级），.env 固定放在项目根
BASE_DIR = Path(__file__).resolve().parents[2]
ENV_FILE = BASE_DIR / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ENV_FILE, env_file_encoding="utf-8", extra="ignore"
    )

    def model_post_init(self, __context) -> None:
        # 把 HF 镜像写入进程环境，供 huggingface_hub 模型下载使用
        if self.HF_ENDPOINT:
            os.environ.setdefault("HF_ENDPOINT", self.HF_ENDPOINT)

    # 项目
    PROJECT_NAME: str = "鹅养殖疫病风险评估交互式问答系统"
    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    # DeepSeek
    DEEPSEEK_API_KEY: str = ""
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com"
    DEEPSEEK_MODEL: str = "deepseek-chat"

    # 本地向量化 / 精排（sentence-transformers，无需 API Key；首次使用自动下载模型）
    EMBEDDING_MODEL: str = "BAAI/bge-small-zh-v1.5"
    RERANK_MODEL: str = "BAAI/bge-reranker-base"
    # HuggingFace 镜像（大陆网络加速模型下载，可留空）
    HF_ENDPOINT: str = ""

    # MySQL
    MYSQL_HOST: str = "localhost"
    MYSQL_PORT: int = 3306
    MYSQL_USER: str = "root"
    MYSQL_PASSWORD: str = ""
    MYSQL_DATABASE: str = "goose_qa"

    # ChromaDB
    CHROMA_PERSIST_DIR: str = "../data/chroma"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # 检索参数
    CHUNK_SIZE: int = 512
    CHUNK_OVERLAP: int = 50
    TOP_K: int = 5

    @property
    def mysql_url(self) -> str:
        return (
            f"mysql+pymysql://{self.MYSQL_USER}:{self.MYSQL_PASSWORD}"
            f"@{self.MYSQL_HOST}:{self.MYSQL_PORT}/{self.MYSQL_DATABASE}?charset=utf8mb4"
        )


settings = Settings()
