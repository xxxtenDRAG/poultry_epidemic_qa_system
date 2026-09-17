"""文本分块：按段落粗切后拼装，chunk_size=512 字符、overlap=50（阶段 2 可调优）。"""
from core.config import settings


def chunk_text(text: str, chunk_size: int | None = None, overlap: int | None = None) -> list[str]:
    """将长文本切成带重叠的块，返回块列表。"""
    chunk_size = chunk_size or settings.CHUNK_SIZE
    overlap = overlap if overlap is not None else settings.CHUNK_OVERLAP
    if chunk_size <= overlap:
        raise ValueError("chunk_size 必须大于 overlap")

    # 先按段落拆分，减少块内语义断裂
    paragraphs = [p.strip() for p in text.splitlines() if p.strip()]
    chunks: list[str] = []
    buffer = ""

    for para in paragraphs:
        # 段落本身超长时按窗口硬切
        while len(para) > chunk_size:
            if buffer:
                chunks.append(buffer)
                buffer = ""
            chunks.append(para[:chunk_size])
            para = para[chunk_size:]
        if buffer and len(buffer) + len(para) + 1 > chunk_size:
            chunks.append(buffer)
            buffer = para
        else:
            buffer = f"{buffer}\n{para}" if buffer else para

    if buffer:
        chunks.append(buffer)

    # 相邻块补 overlap 重叠，保证上下文连续
    overlapped: list[str] = []
    for i, chunk in enumerate(chunks):
        if i > 0 and overlap > 0:
            prev_tail = chunks[i - 1][-overlap:]
            chunk = prev_tail + chunk
        overlapped.append(chunk)
    return overlapped
