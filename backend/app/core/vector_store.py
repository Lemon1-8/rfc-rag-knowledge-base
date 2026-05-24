"""
Qdrant 向量库封装。

两个 collection：
- rfc_chunks_small：小 chunk + 1024 维向量 + parent_chunk_id，用于检索
- rfc_chunks_big：大 chunk（完整 section 原文），无向量，仅主键查询，用于取 LLM 上下文
"""

from qdrant_client import QdrantClient
from qdrant_client.http import models
from app.config import settings

SMALL_COLLECTION = "rfc_chunks_small"
BIG_COLLECTION = "rfc_chunks_big"
VECTOR_DIM = 1024


class VectorStore:
    def __init__(self, url: str | None = None):
        self.client = QdrantClient(
            url=url or settings.qdrant_url,
            api_key=settings.qdrant_api_key or None,
        )
        self._ensure_collections()

    def _ensure_collections(self):
        """启动时自动创建两个 collection。"""
        existing = {c.name for c in self.client.get_collections().collections}

        if SMALL_COLLECTION not in existing:
            self.client.create_collection(
                collection_name=SMALL_COLLECTION,
                vectors_config=models.VectorParams(
                    size=VECTOR_DIM,
                    distance=models.Distance.COSINE,
                ),
            )
            self.client.create_payload_index(
                collection_name=SMALL_COLLECTION,
                field_name="parent_chunk_id",
                field_schema=models.PayloadSchemaType.KEYWORD,
            )

        if BIG_COLLECTION not in existing:
            self.client.create_collection(
                collection_name=BIG_COLLECTION,
                vectors_config={},
            )
            self.client.create_payload_index(
                collection_name=BIG_COLLECTION,
                field_name="chunk_id",
                field_schema=models.PayloadSchemaType.KEYWORD,
            )

    def upsert_small_chunks(
        self,
        chunks: list[dict],
        vectors: list[list[float]],
    ):
        """批量写入小 chunk + 向量。"""
        points = []
        for chunk, vector in zip(chunks, vectors):
            pid = abs(hash(chunk["id"])) % (2**63)
            points.append(models.PointStruct(
                id=pid,
                vector=vector,
                payload={
                    "chunk_id": chunk["id"],
                    "parent_chunk_id": chunk["parent_chunk_id"],
                    "content": chunk["content"],
                    "content_type": chunk.get("content_type", "narrative"),
                    "section_path": chunk.get("section_path", ""),
                    "url": chunk.get("url", ""),
                    "content_hash": chunk.get("content_hash", ""),
                },
            ))
        self.client.upsert(collection_name=SMALL_COLLECTION, points=points)

    def upsert_big_chunks(self, chunks: list[dict]):
        """批量写入大 chunk（无向量）。"""
        points = []
        for chunk in chunks:
            pid = abs(hash(chunk["id"])) % (2**63)
            points.append(models.PointStruct(
                id=pid,
                vector={},
                payload={
                    "chunk_id": chunk["id"],
                    "document_id": chunk.get("document_id", ""),
                    "title": chunk.get("title", ""),
                    "section_path": chunk.get("section_path", ""),
                    "content": chunk.get("content", ""),
                    "url": chunk.get("url", ""),
                    "small_chunk_ids": chunk.get("small_chunk_ids", []),
                },
            ))
        self.client.upsert(collection_name=BIG_COLLECTION, points=points)

    def search_small(
        self,
        query_vector: list[float],
        top_k: int = 20,
    ) -> list[dict]:
        """在 small collection 中向量检索。"""
        response = self.client.query_points(
            collection_name=SMALL_COLLECTION,
            query=query_vector,
            limit=top_k,
        )
        results = []
        for r in response.points:
            p = r.payload or {}
            results.append({
                "id": p.get("chunk_id", ""),
                "parent_chunk_id": p.get("parent_chunk_id", ""),
                "content": p.get("content", ""),
                "section_path": p.get("section_path", ""),
                "url": p.get("url", ""),
                "score": r.score,
            })
        return results

    def fetch_big_chunks(self, chunk_ids: list[str]) -> list[dict]:
        """按 chunk_id 批量查询大 chunk。"""
        if not chunk_ids:
            return []
        points, _ = self.client.scroll(
            collection_name=BIG_COLLECTION,
            scroll_filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="chunk_id",
                        match=models.MatchAny(any=chunk_ids),
                    )
                ]
            ),
            limit=len(chunk_ids),
        )
        results = []
        for r in points:
            p = r.payload or {}
            results.append({
                "id": p.get("chunk_id", ""),
                "document_id": p.get("document_id", ""),
                "title": p.get("title", ""),
                "section_path": p.get("section_path", ""),
                "content": p.get("content", ""),
                "url": p.get("url", ""),
            })
        return results

    def delete_by_document(self, document_id: str):
        """删除某个文档的所有 chunk。"""
        # 先从 big collection 找出该文档的所有 chunk_id
        points, _ = self.client.scroll(
            collection_name=BIG_COLLECTION,
            scroll_filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="document_id",
                        match=models.MatchValue(value=document_id),
                    )
                ]
            ),
            limit=10000,
        )
        chunk_ids = [(p.payload or {}).get("chunk_id", "") for p in points]

        # 删除 big collection 中的点
        if points:
            self.client.delete(
                collection_name=BIG_COLLECTION,
                points_selector=models.PointIdsList(
                    points=[p.id for p in points]
                ),
            )

        # 删除 small collection 中关联的点
        if chunk_ids:
            small_points, _ = self.client.scroll(
                collection_name=SMALL_COLLECTION,
                scroll_filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="parent_chunk_id",
                            match=models.MatchAny(any=chunk_ids),
                        )
                    ]
                ),
                limit=10000,
            )
            if small_points:
                self.client.delete(
                    collection_name=SMALL_COLLECTION,
                    points_selector=models.PointIdsList(
                        points=[p.id for p in small_points]
                    ),
                )

    def scroll_all_small(self) -> list[dict]:
        """获取所有小 chunk（用于构建 BM25 索引）。"""
        all_chunks: list[dict] = []
        offset: str | int | None = None
        while True:
            points, next_offset = self.client.scroll(
                collection_name=SMALL_COLLECTION,
                limit=100,
                offset=offset,
                with_payload=True,
                with_vectors=False,
            )
            for point in points:
                p = point.payload or {}
                all_chunks.append({
                    "chunk_id": p.get("chunk_id", ""),
                    "parent_chunk_id": p.get("parent_chunk_id", ""),
                    "content": p.get("content", ""),
                })
            if next_offset is None:
                break
            offset = next_offset
        return all_chunks

    def count_small(self) -> int:
        info = self.client.get_collection(SMALL_COLLECTION)
        return info.points_count or 0

    def count_big(self) -> int:
        info = self.client.get_collection(BIG_COLLECTION)
        return info.points_count or 0


vector_store = VectorStore()
