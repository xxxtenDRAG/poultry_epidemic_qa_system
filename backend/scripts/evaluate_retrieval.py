"""检索效果评估：用测试集计算 Hit Rate，对比「纯向量」vs「向量+重排」。

用法（backend 目录、venv 激活）：
    python -m scripts.evaluate_retrieval            # 跑纯向量 + 重排两轮对比
    python -m scripts.evaluate_retrieval --rerank   # 只跑重排
    python -m scripts.evaluate_retrieval --top-k 5
"""
import argparse
import json
from pathlib import Path

from data_pipeline.embed import embed_texts
from data_pipeline.store import search

SAMPLES = Path(__file__).resolve().parent.parent.parent / "datasets" / "test_qa" / "qa_samples.json"


def load_samples() -> list[dict]:
    return json.loads(SAMPLES.read_text(encoding="utf-8"))


def evaluate(rerank: bool, top_k: int) -> dict:
    samples = load_samples()
    hit_at = {k: 0 for k in (1, 3, 5)}
    detail_rows: list[dict] = []
    for s in samples:
        emb = embed_texts([s["question"]])[0]
        res = search(emb, top_k=top_k, query=s["question"], rerank=rerank)
        hit_rank = None  # 首个命中文档的 0-based 位次
        for rank, r in enumerate(res):
            if s["source_doc"] in r["metadata"]["doc"]:
                hit_rank = rank
                break
        if hit_rank is not None:
            for k in hit_at:
                if hit_rank < k:
                    hit_at[k] += 1
        detail_rows.append(
            {
                "question": s["question"][:24],
                "hit": hit_rank is not None,
                "hit_rank": hit_rank,
                "first_doc": res[0]["metadata"]["doc"] if res else None,
            }
        )
    total = len(samples)
    return {
        "total": total,
        "hit_at": {f"Hit@{k}": v / total for k, v in hit_at.items()},
        "hit_count": {f"Hit@{k}": v for k, v in hit_at.items()},
        "details": detail_rows,
    }


def print_report(tag: str, rep: dict) -> None:
    print(f"\n===== {tag} =====")
    print(f"样本 {rep['total']} 条")
    for k in ("1", "3", "5"):
        print(f"  Hit@{k} = {rep['hit_count']['Hit@' + k]}/{rep['total']}  ({rep['hit_at']['Hit@' + k]:.1%})")
    misses = [d for d in rep["details"] if not d["hit"]]
    if misses:
        print(f"未命中 {len(misses)} 条：")
        for d in misses:
            print(f"  - {d['question']}...  (top1={d['first_doc']})")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rerank", action="store_true", help="只跑向量+重排")
    ap.add_argument("--top-k", type=int, default=5)
    args = ap.parse_args()

    if not args.rerank:
        print_report("纯向量（baseline）", evaluate(rerank=False, top_k=args.top_k))
    print_report("向量 + bge-reranker 精排", evaluate(rerank=True, top_k=args.top_k))


if __name__ == "__main__":
    main()
