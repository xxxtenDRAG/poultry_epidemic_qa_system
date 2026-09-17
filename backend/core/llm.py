"""DeepSeek LLM 客户端（OpenAI 兼容接口，惰性初始化）。

供 agent.graph、knowledge_graph.retriever、scripts.build_graph 等共用，
避免各模块重复初始化并在模块加载时产生循环导入。
"""
from openai import OpenAI

from core.config import settings

_client: OpenAI | None = None


def get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(api_key=settings.DEEPSEEK_API_KEY, base_url=settings.DEEPSEEK_BASE_URL)
    return _client