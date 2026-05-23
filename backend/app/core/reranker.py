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
    ) -> list[dict]:
        """重排序文档，返回 top_k 个结果。"""
        if not documents:
            return []

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
            return [
                {
                    "index": r["index"],
                    "score": r["score"],
                    "text": documents[r["index"]] if r["index"] < len(documents) else "",
                }
                for r in sorted_results[:top_k]
            ]


reranker_client = RerankerClient()
