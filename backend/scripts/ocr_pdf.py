"""扫描版/图片型 PDF 的离线 OCR 预处理。

将没有文字层的 PDF 逐页渲染、用 RapidOCR（PP-OCRv4 中英文模型，ONNXRuntime，
纯 CPU 可跑）识别为文本，最终合并成一个 .txt，再通过系统现有的文档上传通道
（或入库流水线）进入向量库与知识图谱。

特性：
- 每页结果缓存到 <输出目录>/<pdf名>/pXXXX.txt，中断后重跑自动跳过已完成页；
- 页面若已含文字层（非扫描页）则直接复用文字层，不浪费 OCR；
- 打印进度、单页耗时与预计剩余时间。

用法（在 backend 目录下）：
  .venv\\Scripts\\python.exe -m scripts.ocr_pdf "<pdf路径>"
  .venv\\Scripts\\python.exe -m scripts.ocr_pdf "<pdf路径>" --start 20 --end 60
  .venv\\Scripts\\python.exe -m scripts.ocr_pdf "<pdf路径>" --dpi 200 --force
"""

from __future__ import annotations

import argparse
import re
import sys
import time
from collections import Counter
from pathlib import Path

import numpy as np
import pymupdf

# 已有文字层的页面直接复用，文字字符数超过该阈值即视为非扫描页
TEXT_LAYER_MIN_CHARS = 50

# 独立成行的页码：纯数字或仅夹着点/间隔号/连字符（如 69、72·、- 3 -）
PAGE_NUM_RE = re.compile(r"^[\s\d·.。,，、\-—_/]*\d{1,4}[\s\d·.。,，、\-—_/]*$")
# 页眉候选行长度上限
BOILERPLATE_MAX_LEN = 12
# 页眉行至少在多少页出现：max(8 页, 总页数 15%)
BOILERPLATE_MIN_PAGES = 8
BOILERPLATE_MIN_RATIO = 0.15

# 每页缓存与最终产物都放在项目根的 datasets/ocr_output 下
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
OUTPUT_DIR = PROJECT_ROOT / "datasets" / "ocr_output"

_engine = None


def get_engine():
    """OCR 引擎单例，避免每页重复加载模型。"""
    global _engine
    if _engine is None:
        from rapidocr_onnxruntime import RapidOCR

        _engine = RapidOCR()
    return _engine


def render_page(page: pymupdf.Page, dpi: int) -> np.ndarray:
    """把 PDF 页面渲染成 RGB ndarray（RapidOCR 接受 numpy 数组）。"""
    pix = page.get_pixmap(dpi=dpi, alpha=False)
    img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
    return img[:, :, :3]  # alpha=False 时通常已是 3 通道，保险起见截一刀


def ocr_page(page: pymupdf.Page, dpi: int) -> tuple[str, bool]:
    """识别单页，返回 (文本, 是否用了文字层)。文本行按纵坐标自上而下排序。"""
    existing = page.get_text().strip()
    if len(existing) >= TEXT_LAYER_MIN_CHARS:
        return existing, True

    engine = get_engine()
    result, _ = engine(render_page(page, dpi))
    if not result:
        return "", False

    # result: [[box(4点), text, score], ...]，按行框中心 y 排序，近似阅读顺序
    rows = []
    for box, text, _score in result:
        ys = [pt[1] for pt in box]
        xs = [pt[0] for pt in box]
        rows.append((min(ys), min(xs), text.strip()))
    rows.sort(key=lambda r: (round(r[0] / 15), r[1]))  # 容差 15px 内视为同一行
    return "\n".join(text for _y, _x, text in rows if text), False


def merge_caches(cache_dir: Path, merged_path: Path, clean: bool = True) -> int:
    """把按页缓存合并为单个 txt；clean=True 时剔除页码行与高频页眉。

    返回被剔除的行数。只处理合并产物，不修改每页缓存。
    """
    page_files = sorted(cache_dir.glob("p*.txt"))
    page_texts = [cf.read_text(encoding="utf-8").strip() for cf in page_files]
    removed = 0

    if clean:
        # 剥掉行首尾包裹符号，归并“科技兴农奔小康丛书/（…）/《…》”等页眉变体
        def unwrap(line: str) -> str:
            return line.strip().strip("()（）《》\"'“”‘’[]【】 ")

        # 跨页统计高频短行：只统计每页首行/末行（页眉页脚位置），避免把正文中
        # 反复出现的小节标题（如“诊断依据”“防治策略”）误判为页眉
        counter: Counter[str] = Counter()
        for text in page_texts:
            lines = [ln for ln in (s.strip() for s in text.splitlines()) if ln]
            edge_lines = {u for ln in lines[:1] + lines[-1:] if 0 < len(u := unwrap(ln)) <= BOILERPLATE_MAX_LEN}
            counter.update(edge_lines)
        threshold = max(BOILERPLATE_MIN_PAGES, len(page_texts) * BOILERPLATE_MIN_RATIO)
        boilerplate = {ln for ln, n in counter.items() if n >= threshold}
        if boilerplate:
            print(f"识别到页眉/页脚高频行（出现≥{threshold:.0f} 页）：{sorted(boilerplate)}")

        # OCR 页眉常有错字变体（奔康/奔叫康/奔摩），再用相似度兜底
        from difflib import SequenceMatcher

        def is_boilerplate(line: str) -> bool:
            if line in boilerplate:
                return True
            if len(line) > BOILERPLATE_MAX_LEN + 2:
                return False
            return any(
                abs(len(line) - len(seed)) <= 2
                and SequenceMatcher(None, line, seed).ratio() >= 0.7
                for seed in boilerplate
            )

        cleaned_pages = []
        for text in page_texts:
            kept = []
            for ln in text.splitlines():
                s = ln.strip()
                if not s:
                    continue
                if PAGE_NUM_RE.match(s) or is_boilerplate(unwrap(s)):
                    removed += 1
                    continue
                kept.append(s)
            cleaned_pages.append("\n".join(kept))
        page_texts = cleaned_pages

    merged = "\n\n".join(t for t in page_texts if t)
    merged_path.write_text(merged, encoding="utf-8")
    print(f"合并产物：{merged_path}（{len(page_files)} 页，共 {len(merged)} 字符，剔除噪声行 {removed} 行）")
    return removed


def main() -> int:
    parser = argparse.ArgumentParser(description="扫描版 PDF 离线 OCR 预处理")
    parser.add_argument("pdf", help="PDF 文件路径")
    parser.add_argument("--start", type=int, default=1, help="起始页（1-based，含）")
    parser.add_argument("--end", type=int, default=0, help="结束页（1-based，含），0=最后一页")
    parser.add_argument("--dpi", type=int, default=250, help="渲染 DPI，默认 250")
    parser.add_argument("--force", action="store_true", help="忽略每页缓存，全部重新识别")
    parser.add_argument("--no-clean", action="store_true", help="合并时不剔除页码/页眉噪声")
    parser.add_argument("--merge-only", action="store_true", help="跳过 OCR，仅用现有按页缓存重新合并")
    parser.add_argument("--output", default="", help="合并产物路径，默认 datasets/ocr_output/<pdf名>.ocr.txt")
    args = parser.parse_args()

    pdf_path = Path(args.pdf).resolve()
    if not pdf_path.exists():
        print(f"[错误] 文件不存在：{pdf_path}")
        return 1

    # Windows 目录名不可以空格/点结尾，也不允许 :<>"/\|?* 等字符，统一清洗
    illegal = '<>:"/\\|?*'
    safe_stem = pdf_path.stem.translate(str.maketrans(illegal, "_" * len(illegal))).strip().rstrip(". ")
    cache_dir = OUTPUT_DIR / safe_stem
    cache_dir.mkdir(parents=True, exist_ok=True)
    merged_path = Path(args.output).resolve() if args.output else OUTPUT_DIR / f"{safe_stem}.ocr.txt"

    if args.merge_only:
        print(f"仅重新合并（不 OCR）：{cache_dir}")
        merge_caches(cache_dir, merged_path, clean=not args.no_clean)
        return 0

    doc = pymupdf.open(pdf_path)
    total = doc.page_count
    end = args.end or total
    if not (1 <= args.start <= end <= total):
        print(f"[错误] 页码范围非法：{args.start}-{end}，全书共 {total} 页")
        return 1

    print(f"文件：{pdf_path.name}（共 {total} 页）")
    print(f"范围：第 {args.start}-{end} 页，DPI={args.dpi}，缓存目录：{cache_dir}")

    done = 0
    skipped = 0
    text_layer_pages = 0
    t0 = time.time()

    for pno in range(args.start, end + 1):
        cache_file = cache_dir / f"p{pno:04d}.txt"
        if cache_file.exists() and not args.force:
            skipped += 1
            continue

        page = doc[pno - 1]
        page_t0 = time.time()
        text, used_text_layer = ocr_page(page, args.dpi)
        cache_file.write_text(text, encoding="utf-8")
        done += 1
        text_layer_pages += int(used_text_layer)

        elapsed = time.time() - t0
        processed = done  # 仅按新识别页估算
        avg = elapsed / processed if processed else 0
        remain_pages = end - pno
        eta_min = avg * remain_pages / 60
        flag = "文字层" if used_text_layer else ("空页" if not text else f"{len(text)}字")
        print(
            f"  p{pno:4d}/{end}  {page_t0 and time.time() - page_t0:5.1f}s  {flag:>6s}  "
            f"均速 {avg:5.1f}s/页  剩余约 {eta_min:5.1f} 分钟"
        )

    doc.close()

    # 合并所有已缓存页（始终按全书页码顺序，允许分批跑不同区间后再合并）
    print("-" * 60)
    print(f"新识别 {done} 页（其中复用文字层 {text_layer_pages} 页），缓存跳过 {skipped} 页")
    merge_caches(cache_dir, merged_path, clean=not args.no_clean)
    return 0


if __name__ == "__main__":
    sys.exit(main())
