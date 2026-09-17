"""离线入库脚本：文档 → 解析 → 分块 → bge 向量化 → ChromaDB。

用法（在 backend/ 目录下，已激活 venv）：
    python -m scripts.ingest [文件或目录] [--doc-name 自定义名]
    不带参数时默认处理 ../../datasets/knowledge/ 下全部文档
"""
import argparse
import sys
from pathlib import Path

# 保证能 import backend 包
BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from data_pipeline.pipeline import process_document
from data_pipeline.store import count

DEFAULT_DATA_DIR = BACKEND_DIR.parent / "datasets" / "knowledge"


def ingest(path: str | Path, doc_name: str | None = None) -> None:
    path = Path(path)
    if path.is_file():
        files = [path]
    elif path.is_dir():
        files = [p for p in path.iterdir() if p.is_file() and p.suffix.lower() in (".txt", ".md", ".pdf")]
    else:
        print(f"路径不存在: {path}")
        sys.exit(1)

    if not files:
        print(f"目录下没有可解析的文档: {path}")
        sys.exit(1)

    for file in files:
        print(f"[1/4] 解析: {file.name}")
        result = process_document(file, doc_name)
        print(f"[2/4] 分块: {result['chars']} 字符 -> {result['chunk_count']} 块")
        print(f"[3/4] 向量化 + 入库 ChromaDB")
        print(f"完成 ✅ {result['doc_name']}（当前库共 {count()} 块）\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="离线入库脚本")
    parser.add_argument("path", nargs="?", default=str(DEFAULT_DATA_DIR), help="文件或目录，默认 datasets/knowledge/")
    parser.add_argument("--doc-name", default=None, help="自定义文档名（默认取文件名）")
    args = parser.parse_args()

    ingest(args.path, args.doc_name)


if __name__ == "__main__":
    main()
