"""
混合检索：Dense（向量）+ Sparse（BM25）+ RRF 融合 → Reranker → 分数过滤。

检索链路：
  query → Dense Top-N ─┐
  query → BM25 Top-N  ─┤
                        ├→ RRF 融合 → 去重 parent → 取 big chunks → Rerank → 分数过滤 → 返回
"""

from app.config import settings
from app.core.embedding import embedding_client
from app.core.reranker import reranker_client
from app.core.vector_store import vector_store
from app.core.sparse_search import sparse_retriever


def _rrf_fusion(
    dense_results: list[dict],
    sparse_results: list[tuple[str, float]],
    k: int = 60,
) -> list[str]:
    """RRF（Reciprocal Rank Fusion）：基于排名融合 Dense 和 Sparse 结果。

    返回按 RRF 分数降序排列的 parent_chunk_id 列表。
    """
    scores: dict[str, float] = {}

    for rank, r in enumerate(dense_results):
        pid = r["parent_chunk_id"]
        scores[pid] = scores.get(pid, 0.0) + 1.0 / (k + rank + 1)

    for rank, (pid, _) in enumerate(sparse_results):
        scores[pid] = scores.get(pid, 0.0) + 1.0 / (k + rank + 1)

    merged = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return [pid for pid, _ in merged]


def _dedup_dense(dense_results: list[dict], top_k: int) -> list[str]:
    """仅用 Dense 结果时，按原始分数去重。"""
    seen: set[str] = set()
    pids: list[str] = []
    for r in dense_results:
        pid = r["parent_chunk_id"]
        if pid not in seen:
            seen.add(pid)
            pids.append(pid)
            if len(pids) >= top_k:
                break
    return pids


async def hybrid_search(
    query: str,
    top_k: int = 5,
    dense_top: int | None = None,
    sparse_top: int | None = None,
    score_threshold: float | None = None,
) -> list[dict]:
    """混合检索 + Rerank + 分数过滤。

    Args:
        query: 用户问题
        top_k: 最终返回的文档数
        dense_top: Dense 检索数量（默认从配置读取）
        sparse_top: Sparse 检索数量
        score_threshold: Reranker 最低分数阈值（None=用配置默认值）
    """
    if dense_top is None:
        dense_top = settings.dense_top
    if sparse_top is None:
        sparse_top = settings.sparse_top
    if score_threshold is None:
        score_threshold = settings.reranker_score_threshold

    # 1. Dense 检索
    query_vector = await embedding_client.encode_single(query)
    dense_results = vector_store.search_small(query_vector, top_k=dense_top)

    if not dense_results:
        return []

    # 2. Sparse 检索（BM25）
    sparse_results = sparse_retriever.search(query, top_k=sparse_top)

    # 3. 融合：RRF 或 Dense-only 去重
    if sparse_results:
        merged_pids = _rrf_fusion(dense_results, sparse_results)
        merged_pids = merged_pids[:dense_top]
    else:
        merged_pids = _dedup_dense(dense_results, dense_top)

    if not merged_pids:
        return []

    # 4. 取 big chunks
    big_chunks = vector_store.fetch_big_chunks(merged_pids)

    if not big_chunks:
        return []

    # 5. Rerank（多取一些以留出过滤空间）
    rerank_n = min(len(big_chunks), max(top_k * 3, 10))
    big_texts = [b.get("content", "") for b in big_chunks]
    rerank_results = await reranker_client.rerank(
        query,
        big_texts,
        top_k=rerank_n,
        score_threshold=score_threshold,
    )

    # 6. 映射最终结果
    final: list[dict] = []
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
        if len(final) >= top_k:
            break

    return final
