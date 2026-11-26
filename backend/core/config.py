"""全局配置：从环境变量 / .env 读取，密钥严禁硬编码。"""
import os
from pathlib import Path
from urllib.parse import quote_plus

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

    # Vision（图片识别）—— 默认关闭，需配置 VISION_API_KEY 后启用
    VISION_ENABLED: bool = False
    VISION_MODEL: str = "qwen3.5-flash"
    VISION_BASE_URL: str = "https://maas.qianwenaiapi.com/compatible-mode/v1"
    VISION_API_KEY: str = ""

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

    # 多轮对话：生成时携带的最近对话轮数（1 轮 = 用户问 + 助手答）与历史总字符上限
    HISTORY_MAX_TURNS: int = 5
    HISTORY_MAX_CHARS: int = 2000

    # ---- 天气预警 ----
    # 数据源：auto（Open-Meteo → 中国天气网 → 演示数据）/ open-meteo / itboy / demo
    WEATHER_PROVIDER: str = "auto"
    # 天气缓存秒数（30 分钟）
    WEATHER_CACHE_TTL: int = 1800
    # Open-Meteo 超时秒数（国内网络常不可达，超时后自动降级）
    WEATHER_TIMEOUT: float = 6.0

    # ---- 阶段 3：知识图谱 + 评估循环 ----
    # 图谱数据文件路径；留空则用默认 <项目根>/data/knowledge_graph.json
    GRAPH_DATA_PATH: str = ""
    # 评估循环开关：false 时跳过相关性/充分度评估直接出答案（降级）
    EVAL_LOOP_ENABLED: bool = True
    EVAL_MAX_LOOPS: int = 3
    # 图谱子图最大节点数，避免上下文膨胀
    GRAPH_HOP: int = 1

    @property
    def graph_data_file(self) -> str:
        """图谱数据文件绝对路径（默认 <项目根>/data/knowledge_graph.json）。"""
        return self.GRAPH_DATA_PATH or str(BASE_DIR / "data" / "knowledge_graph.json")

    @property
    def mysql_url(self) -> str:
        return (
            f"mysql+pymysql://{quote_plus(self.MYSQL_USER)}:{quote_plus(self.MYSQL_PASSWORD)}"
            f"@{self.MYSQL_HOST}:{self.MYSQL_PORT}/{self.MYSQL_DATABASE}?charset=utf8mb4"
        )


settings = Settings()
