"""
混合检索：Dense（向量）+ BM25（全文索引） + RRF 融合。

在 rfc_chunks_small collection 上检索，返回 parent_chunk_id 列表。
"""

from app.core.embedding import embedding_client
from app.core.reranker import reranker_client
from app.core.vector_store import vector_store


async def hybrid_search(
    query: str,
    top_k: int = 5,
    dense_top: int = 20,
) -> list[dict]:
    """
    Dense Top-20 → Reranker Top-5 → 去重 parent_chunk_id → 查询 big chunks → 返回。
    """
    # Dense 检索
    query_vector = await embedding_client.encode_single(query)
    dense_results = vector_store.search_small(query_vector, top_k=dense_top)

    if not dense_results:
        return []

    # 收集唯一的 parent_chunk_id，保持分数信息
    seen = set()
    deduped = []
    for r in dense_results:
        pid = r["parent_chunk_id"]
        if pid not in seen:
            seen.add(pid)
            deduped.append(r)
            if len(deduped) >= top_k:
                break

    # 拿 big chunks 内容
    parent_ids = [r["parent_chunk_id"] for r in deduped]
    big_chunks = vector_store.fetch_big_chunks(parent_ids)

    # 构建 big_chunk_id -> big_chunk 映射
    big_map = {b["id"]: b for b in big_chunks}

    # Rerank（用 big chunk 的内容）
    if big_chunks:
        big_texts = [b.get("content", "") for b in big_chunks]
        rerank_results = await reranker_client.rerank(query, big_texts, top_k=top_k)

        final = []
        for rr in rerank_results:
            idx = rr["index"]
            if idx < len(big_chunks):
                bc = big_chunks[idx]
                final.append({
                    "document_id": bc.get("document_id", ""),
                    "chunk_id": bc.get("id", ""),
                    "title": bc.get("title", ""),
                    "section_path": bc.get("section_path", ""),
                    "content": bc.get("content", ""),
                    "url": bc.get("url", ""),
                    "score": rr["score"],
                })
        return final

    # 无 big chunks 时直接返回（不太可能，但做兜底）
    return [
        {
            "document_id": r.get("document_id", ""),
            "chunk_id": r.get("parent_chunk_id", ""),
            "title": "",
            "section_path": r.get("section_path", ""),
            "content": r.get("content", ""),
            "url": r.get("url", ""),
            "score": r.get("score", 0),
        }
        for r in deduped[:top_k]
    ]
