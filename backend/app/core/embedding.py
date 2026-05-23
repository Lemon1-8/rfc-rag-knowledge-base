"""
TEI Embedding HTTP 客户端 —— 调用 localhost:8888 的 /embed 端点。
返回 1024 维向量。
"""

import httpx
from app.config import settings


class EmbeddingClient:
    def __init__(self, base_url: str | None = None):
        self.base_url = (base_url or settings.tei_embedding_url).rstrip("/")

    async def encode(self, texts: list[str]) -> list[list[float]]:
        """批量编码文本为 1024 维向量。"""
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{self.base_url}/embed",
                json={"inputs": texts, "truncate": True},
            )
            resp.raise_for_status()
            return resp.json()  # TEI 返回 [[float, ...], ...]

    async def encode_single(self, text: str) -> list[float]:
        """编码单个文本。"""
        results = await self.encode([text])
        return results[0]


embedding_client = EmbeddingClient()
