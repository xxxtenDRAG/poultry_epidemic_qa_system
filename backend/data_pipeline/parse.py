"""文档解析：支持 .txt/.md 直接读取，.pdf 用 pdfplumber 抽取文本。"""
from pathlib import Path


def parse_document(file_path: str | Path) -> str:
    """解析单个文档，返回纯文本。"""
    path = Path(file_path)
    suffix = path.suffix.lower()

    if suffix == ".pdf":
        import pdfplumber

        texts: list[str] = []
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    texts.append(text)
        return "\n".join(texts)

    if suffix in (".txt", ".md"):
        return path.read_text(encoding="utf-8")

    raise ValueError(f"不支持的文件类型: {suffix}（支持 pdf/txt/md）")
