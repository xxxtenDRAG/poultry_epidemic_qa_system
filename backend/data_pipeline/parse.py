"""文档解析：支持 .txt/.md（多编码回退）、.pdf（pdfplumber）、.docx（python-docx）。"""
from pathlib import Path

# Windows 中文环境常见的 txt 编码顺序
_TEXT_ENCODINGS = ("utf-8-sig", "utf-8", "gb18030", "gbk", "big5")


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

    if suffix == ".docx":
        return _parse_docx(path)

    if suffix in (".txt", ".md"):
        return _read_text(path)

    raise ValueError(f"不支持的文件类型: {suffix}（支持 pdf/docx/txt/md）")


def _read_text(path: Path) -> str:
    """读取纯文本，按常见中文编码依次回退，全部失败再忽略错误字节。"""
    raw = path.read_bytes()
    for enc in _TEXT_ENCODINGS:
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="ignore")


def _parse_docx(path: Path) -> str:
    """抽取 docx 正文段落与表格单元格文本。"""
    import docx

    document = docx.Document(path)
    parts = [p.text.strip() for p in document.paragraphs if p.text.strip()]
    for table in document.tables:
        for row in table.rows:
            cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
            if cells:
                # 同一行单元格去重（合并单元格会重复出现）
                deduped = list(dict.fromkeys(cells))
                parts.append("\t".join(deduped))
    return "\n".join(parts)
