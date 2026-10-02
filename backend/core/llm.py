"""DeepSeek LLM 客户端（OpenAI 兼容接口，惰性初始化）。

供 agent.graph、knowledge_graph.retriever、scripts.build_graph 等共用，
避免各模块重复初始化并在模块加载时产生循环导入。
"""
from openai import OpenAI

from core.config import settings

_client: OpenAI | None = None
_vision_client: OpenAI | None = None


def get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(api_key=settings.DEEPSEEK_API_KEY, base_url=settings.DEEPSEEK_BASE_URL)
    return _client


def get_vision_client() -> OpenAI:
    global _vision_client
    if _vision_client is None:
        if settings.VISION_API_KEY:
            _vision_client = OpenAI(api_key=settings.VISION_API_KEY, base_url=settings.VISION_BASE_URL)
        else:
            _vision_client = get_client()
    return _vision_client