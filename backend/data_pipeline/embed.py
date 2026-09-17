"""文本向量化：sentence-transformers 加载本地 bge 模型。

首次运行会自动从 HuggingFace 下载模型（约 100MB），国内可设置镜像：
$env:HF_ENDPOINT = 'https://hf-mirror.com'
"""
from functools import lru_cache

from core.config import settings


@lru_cache(maxsize=1)
def get_embedder():
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(settings.EMBEDDING_MODEL)


def embed_texts(texts: list[str]) -> list[list[float]]:
    """批量向量化（余弦相似度检索需 normalize）。"""
    model = get_embedder()
    return model.encode(texts, normalize_embeddings=True).tolist()
