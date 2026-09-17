"""M2 Agent Demo：终端问答（RAG：检索 + DeepSeek 生成）。

用法（在 backend/ 目录下，已激活 venv）：
    python -m scripts.agent_chat "小鹅瘟的典型症状和防控措施是什么"
"""
import argparse
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from agent.graph import run


def main() -> None:
    parser = argparse.ArgumentParser(description="M2 Agent 问答 Demo")
    parser.add_argument("query", help="要咨询的鹅养殖疫病问题")
    args = parser.parse_args()

    print(f"问题：{args.query}\n")
    result = run(args.query)

    print("=" * 50)
    print("答案：")
    print(result["answer"])
    print("=" * 50)
    print("\n溯源（知识来源）：")
    for s in result["sources"]:
        print(f"  - {s['doc']}  块{s['index']}  距离={s['distance']:.4f}")


if __name__ == "__main__":
    main()
