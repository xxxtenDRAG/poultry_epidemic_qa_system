"""检索测试脚本：输入问题 → 向量化 → ChromaDB 检索 → 打印 Top-K。

用法（在 backend/ 目录下，已激活 venv）：
    python -m scripts.search "小鹅瘟的典型症状是什么" [--top-k 5]
"""
import argparse
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from data_pipeline.embed import embed_texts
from data_pipeline.store import count, search


def main() -> None:
    parser = argparse.ArgumentParser(description="向量检索测试")
    parser.add_argument("query", help="查询问题")
    parser.add_argument("--top-k", type=int, default=5, help="返回条数，默认 5")
    args = parser.parse_args()

    if count() == 0:
        print("知识库为空，请先运行: python -m scripts.ingest")
        sys.exit(1)

    print(f"检索: {args.query}\n")
    embedding = embed_texts([args.query])[0]
    results = search(embedding, top_k=args.top_k)

    for i, r in enumerate(results, 1):
        print(f"#{i}  距离={r['distance']:.4f}  来源={r['metadata'].get('doc')}  块号={r['metadata'].get('index')}")
        print(f"    {r['document'][:120]}...")
        print()


if __name__ == "__main__":
    main()
