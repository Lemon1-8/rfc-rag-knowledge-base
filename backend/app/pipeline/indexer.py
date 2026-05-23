"""
批量索引器：读取清洗后的 Markdown → 切片 → 向量化 → 入库。
"""

import re
from pathlib import Path

from app.core.embedding import embedding_client
from app.core.vector_store import vector_store
from app.pipeline.chunker import chunk_cleaned_md


async def index_cleaned_docs(
    processed_dir: Path,
    batch_size: int = 32,
) -> dict:
    """遍历 processed 目录的所有 .md 文件，切片、向量化、入库。"""
    md_files = sorted(processed_dir.glob("*.md"))
    total_small = 0
    total_big = 0
    errors = []

    for md_file in md_files:
        try:
            markdown_text = md_file.read_text(encoding="utf-8")
            rfc_id = md_file.stem
            title, url, sections = _parse_md_meta(markdown_text, rfc_id)

            # 切片
            big_chunks, small_chunks = chunk_cleaned_md(
                markdown_text, rfc_id, title, url, sections
            )

            # 向量化小 chunk（批量）
            if small_chunks:
                small_texts = [s.content for s in small_chunks]
                all_vectors = []
                for i in range(0, len(small_texts), batch_size):
                    batch_texts = small_texts[i:i + batch_size]
                    batch_vectors = await embedding_client.encode(batch_texts)
                    all_vectors.extend(batch_vectors)

                small_dicts = [
                    {
                        "id": s.chunk_id,
                        "parent_chunk_id": s.parent_chunk_id,
                        "content": s.content,
                        "content_type": s.content_type.value,
                        "section_path": s.section_path,
                        "url": s.url,
                        "content_hash": s.content_hash,
                    }
                    for s in small_chunks
                ]
                vector_store.upsert_small_chunks(small_dicts, all_vectors)
                total_small += len(small_chunks)

            # 入库 big chunks
            if big_chunks:
                big_dicts = [
                    {
                        "id": b.chunk_id,
                        "document_id": b.document_id,
                        "title": b.title,
                        "section_path": b.section_path,
                        "content": b.content,
                        "url": b.url,
                        "small_chunk_ids": b.small_chunk_ids,
                    }
                    for b in big_chunks
                ]
                vector_store.upsert_big_chunks(big_dicts)
                total_big += len(big_chunks)

        except Exception as e:
            errors.append({"file": str(md_file), "error": str(e)})

    return {
        "small_chunks": total_small,
        "big_chunks": total_big,
        "errors": errors,
    }


def _parse_md_meta(markdown_text: str, rfc_id: str) -> tuple[str, str, list[dict]]:
    """从 Markdown 文本解析标题、链接和章节骨架。"""
    lines = markdown_text.split("\n")
    title = rfc_id.upper()
    url = ""
    sections: list[dict] = []

    for line in lines:
        if line.startswith("# ") and not title:
            title = line[2:].strip()
        if line.startswith("> 来源: ") and not url:
            # line 格式: "> 来源: https://..."，前缀 7 个字符
            url = line[6:].strip()
        # 检测 RFC 编号章节标题（如 "1. Introduction"）
        m = re.match(r"^(\d+(?:\.\d+)*)\s+\.?\s*(.+)", line)
        if m:
            sections.append({
                "heading": line.strip(),
                "level": 2,
                "url": url,
                "content_md": line.strip() + "\n",  # 标记新 section 起点
            })
        elif re.match(r"^(Appendix\s+[A-Z])", line, re.IGNORECASE):
            sections.append({
                "heading": line.strip(),
                "level": 2,
                "url": url,
                "content_md": line.strip() + "\n",
            })
        elif sections:
            # 内容追加到最后一个 section
            sections[-1]["content_md"] += line + "\n"
        else:
            # 在第一个 section 之前的前导内容
            sections.append({
                "heading": title or "Preamble",
                "level": 1,
                "url": url,
                "content_md": line + "\n",
            })

    if not sections:
        sections = [{
            "heading": title or "Full Document",
            "level": 1,
            "url": url,
            "content_md": markdown_text,
        }]

    return title, url, sections
