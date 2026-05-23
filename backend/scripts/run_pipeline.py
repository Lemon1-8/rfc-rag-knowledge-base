"""
一键全量管道：爬取 → 清洗 → 切片 → 向量化 → 入库。

用法：
    cd backend && python -m scripts.run_pipeline --limit 10
"""

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.pipeline.crawler import crawl_top_rfcs
from app.pipeline.cleaner import clean_rfc_text, save_processed
from app.pipeline.indexer import index_cleaned_docs


async def run(limit: int, raw_dir: Path, processed_dir: Path, skip_crawl: bool = False):
    if not skip_crawl:
        print(f"=== 第 1 步：爬取前 {limit} 篇 RFC ===")
        raw_dir.mkdir(parents=True, exist_ok=True)
        processed_dir.mkdir(parents=True, exist_ok=True)

        crawled = await crawl_top_rfcs(limit=limit, raw_dir=raw_dir)

        success_count = 0
        for item in crawled:
            if "error" in item:
                print(f"  [错误] {item['rfc_id']}: {item['error']}")
                continue
            print(f"  [清洗] {item['rfc_id']}: {item['title'][:60]}")
            cleaned = clean_rfc_text(item["text"], item["rfc_id"], item["url"])
            save_processed(cleaned, processed_dir)
            success_count += 1
        print(f"  → 爬取+清洗完成 {success_count}/{limit}\n")

    print("=== 第 2 步：切片 + 向量化 + 入库 ===")
    result = await index_cleaned_docs(processed_dir)
    print(f"  小 chunk 数: {result['small_chunks']}")
    print(f"  大 chunk 数: {result['big_chunks']}")
    if result["errors"]:
        for e in result["errors"]:
            print(f"  [错误] {e['file']}: {e['error']}")

    # 最终统计
    from app.core.vector_store import vector_store
    print(f"\n=== Qdrant 统计 ===")
    print(f"  rfc_chunks_small: {vector_store.count_small()} 条")
    print(f"  rfc_chunks_big:   {vector_store.count_big()} 条")
    print(f"  Dashboard: http://localhost:6333/dashboard")


def main():
    parser = argparse.ArgumentParser(description="RFC 知识库数据管道")
    parser.add_argument("--limit", type=int, default=10, help="爬取 RFC 数量")
    parser.add_argument("--raw-dir", default="data/raw", help="原始 HTML 目录")
    parser.add_argument("--processed-dir", default="data/processed", help="清洗后 Markdown 目录")
    parser.add_argument("--skip-crawl", action="store_true", help="跳过爬取，只做索引")
    args = parser.parse_args()

    root = Path(__file__).resolve().parent.parent
    raw_dir = root / args.raw_dir
    processed_dir = root / args.processed_dir

    asyncio.run(run(args.limit, raw_dir, processed_dir, args.skip_crawl))


if __name__ == "__main__":
    main()
