from fastapi import APIRouter, HTTPException
from app.schemas.document import DocumentListResponse, DocumentDetail, DocumentChunk, CrawlRequest
from qdrant_client.http import models
from app.core.vector_store import vector_store, BIG_COLLECTION

router = APIRouter()


@router.get("/api/documents", response_model=DocumentListResponse)
async def list_documents():
    """文档列表。"""
    results = vector_store.client.scroll(
        collection_name="rfc_chunks_big",
        limit=1000,
    )
    docs = {}
    for point in results[0]:
        payload = point.payload or {}
        doc_id = payload.get("document_id", "")
        if doc_id not in docs:
            docs[doc_id] = {
                "id": doc_id,
                "title": payload.get("title", doc_id),
                "source_url": payload.get("url", ""),
                "chunk_count": 1,
                "indexed_at": None,
                "status": "indexed",
            }
        else:
            docs[doc_id]["chunk_count"] += 1

    return DocumentListResponse(
        documents=list(docs.values()),
        total=len(docs),
    )


@router.post("/api/documents/crawl")
async def crawl_document(req: CrawlRequest):
    """触发爬取单个文档。"""
    return {
        "task_id": f"task_{req.doc_type}_{hash(req.url) & 0xFFFF:04x}",
        "status": "accepted",
    }


@router.get("/api/documents/{document_id}", response_model=DocumentDetail)
async def get_document(document_id: str):
    """获取单个文档的完整内容。"""
    points, _ = vector_store.client.scroll(
        collection_name=BIG_COLLECTION,
        scroll_filter=models.Filter(
            must=[
                models.FieldCondition(
                    key="document_id",
                    match=models.MatchValue(value=document_id),
                )
            ]
        ),
        limit=1000,
    )

    if not points:
        raise HTTPException(status_code=404, detail="文档不存在")

    title = ""
    source_url = ""
    chunks = []

    for p in points:
        payload = p.payload or {}
        title = payload.get("title", title)
        source_url = payload.get("url", source_url)
        chunks.append(DocumentChunk(
            chunk_id=payload.get("chunk_id", ""),
            section_path=payload.get("section_path", ""),
            content=payload.get("content", ""),
        ))

    chunks.sort(key=lambda c: c.section_path)

    return DocumentDetail(
        id=document_id,
        title=title,
        source_url=source_url,
        chunks=chunks,
        chunk_count=len(chunks),
    )


@router.delete("/api/documents/{document_id}", status_code=204)
async def delete_document(document_id: str):
    """删除文档及其所有 chunk。"""
    try:
        vector_store.delete_by_document(document_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
