"""
按 RFC 编号精确补爬，增量索引（不影响已有数据）。

用法：
    cd backend && python -m scripts.crawl_targeted --rfcs 793 8446 6749 6455
    cd backend && python -m scripts.crawl_targeted --all-missing  # 批量为评估补全
"""

import argparse
import asyncio
import sys
import tempfile
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.pipeline.cleaner import clean_rfc_text, save_processed
from app.pipeline.indexer import index_cleaned_docs
from app.core.vector_store import vector_store
from app.core.sparse_search import sparse_retriever

RFC_TXT_BASE = "https://www.rfc-editor.org/rfc/"

# 评估暴露的 8 篇关键缺失 RFC
EVAL_MISSING = [
    ("793", "TCP 基础规范"),
    ("2460", "IPv6 基础"),
    ("5321", "SMTP"),
    ("6455", "WebSocket"),
    ("6749", "OAuth 2.0"),
    ("8259", "JSON"),
    ("8446", "TLS 1.3"),
    ("9110", "HTTP Semantics"),
]


async def fetch_and_clean(client: httpx.AsyncClient, rfc_number: str) -> dict | None:
    """爬取单篇 RFC 并清洗，失败返回 None。"""
    url = f"{RFC_TXT_BASE}rfc{rfc_number}.txt"
    try:
        resp = await client.get(url, follow_redirects=True)
        resp.raise_for_status()
        cleaned = clean_rfc_text(resp.text, f"rfc{rfc_number}", url)
        return cleaned
    except Exception as e:
        print(f"  [错误] rfc{rfc_number}: {e}")
        return None


async def run(rfc_numbers: list[str], processed_dir: Path, rebuild_bm25: bool = True):
    """爬取指定 RFC 并增量索引。"""
    # ---- 第 1 步：爬取 + 清洗 ----
    print(f"=== 补爬 {len(rfc_numbers)} 篇 RFC ===\n")

    async with httpx.AsyncClient(timeout=30.0) as client:
        tasks = [fetch_and_clean(client, num) for num in rfc_numbers]
        results = await asyncio.gather(*tasks)

    cleaned_docs = [r for r in results if r is not None]
    if not cleaned_docs:
        print("没有成功爬取到任何文档。")
        return

    print(f"\n成功爬取: {len(cleaned_docs)}/{len(rfc_numbers)} 篇")

    # ---- 第 2 步：保存到 processed 目录 ----
    processed_dir.mkdir(parents=True, exist_ok=True)
    for doc in cleaned_docs:
        save_processed(doc, processed_dir)

    # ---- 第 3 步：增量索引（只处理新文件） ----
    print("\n=== 增量索引 ===")
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        # 只把本次爬取的文件放到临时目录做索引
        for doc in cleaned_docs:
            src = processed_dir / f"{doc['rfc_id']}.md"
            dst = tmp_path / f"{doc['rfc_id']}.md"
            dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")

        result = await index_cleaned_docs(tmp_path)
        print(f"  新增小 chunk: {result['small_chunks']}")
        print(f"  新增大 chunk: {result['big_chunks']}")
        if result["errors"]:
            for e in result["errors"]:
                print(f"  [错误] {e['file']}: {e['error']}")

    # ---- 第 4 步：重建 BM25 ----
    if rebuild_bm25:
        print("\n=== 重建 BM25 稀疏索引 ===")
        try:
            sparse_retriever.rebuild(vector_store)
            chunk_count = len(sparse_retriever.chunks) if sparse_retriever.chunks else 0
            print(f"  BM25 索引已重建: {chunk_count} chunks")
        except Exception as e:
            print(f"  BM25 重建失败: {e}")

    # ---- 统计 ----
    print(f"\n=== Qdrant 统计 ===")
    print(f"  rfc_chunks_small: {vector_store.count_small()} 条")
    print(f"  rfc_chunks_big:   {vector_store.count_big()} 条")


def main():
    parser = argparse.ArgumentParser(description="精确补爬指定 RFC 编号")
    parser.add_argument("--rfcs", nargs="+", default=None,
                        help="RFC 编号列表（如 793 8446 6749）")
    parser.add_argument("--all-missing", action="store_true",
                        help=f"补爬评估暴露的 {len(EVAL_MISSING)} 篇关键缺失 RFC")
    parser.add_argument("--processed-dir", default="data/processed",
                        help="清洗后 Markdown 目录")
    parser.add_argument("--no-bm25", action="store_true",
                        help="跳过 BM25 索引重建")
    args = parser.parse_args()

    rfc_numbers = []
    if args.rfcs:
        rfc_numbers = args.rfcs
    if args.all_missing:
        rfc_numbers.extend([num for num, _ in EVAL_MISSING])

    if not rfc_numbers:
        print("请指定 --rfcs 或 --all-missing")
        print(f"可用预设: {', '.join(f'RFC {num}' for num, _ in EVAL_MISSING)}")
        sys.exit(1)

    # 去重
    rfc_numbers = list(dict.fromkeys(rfc_numbers))

    print("=" * 60)
    print(f"目标 RFC: {', '.join(f'rfc{n}' for n in rfc_numbers)}")
    print("=" * 60)

    root = Path(__file__).resolve().parent.parent
    processed_dir = root / args.processed_dir

    asyncio.run(run(rfc_numbers, processed_dir, rebuild_bm25=not args.no_bm25))


if __name__ == "__main__":
    main()
