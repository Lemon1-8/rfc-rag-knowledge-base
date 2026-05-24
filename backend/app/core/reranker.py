"""
TEI Reranker HTTP 客户端 —— 调用 localhost:8889 的 /rerank 端点。
"""

import httpx
from app.config import settings


class RerankerClient:
    def __init__(self, base_url: str | None = None):
        self.base_url = (base_url or settings.tei_reranker_url).rstrip("/")

    async def rerank(
        self,
        query: str,
        documents: list[str],
        top_k: int = 5,
        score_threshold: float | None = None,
    ) -> list[dict]:
        """重排序文档，返回 top_k 个结果，可选过滤低于阈值的结果。"""
        if not documents:
            return []

        threshold = score_threshold if score_threshold is not None else settings.reranker_score_threshold

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{self.base_url}/rerank",
                json={
                    "query": query,
                    "texts": documents,
                    "truncate": True,
                },
            )
            resp.raise_for_status()
            results = resp.json()

            sorted_results = sorted(results, key=lambda x: x["score"], reverse=True)

            final = []
            for r in sorted_results:
                if r["score"] < threshold:
                    continue
                final.append({
                    "index": r["index"],
                    "score": r["score"],
                    "text": documents[r["index"]] if r["index"] < len(documents) else "",
                })
                if len(final) >= top_k:
                    break

            # 至少保留 1 条（如果全部低于阈值）
            if not final and sorted_results:
                best = sorted_results[0]
                final.append({
                    "index": best["index"],
                    "score": best["score"],
                    "text": documents[best["index"]] if best["index"] < len(documents) else "",
                })

            return final


reranker_client = RerankerClient()
