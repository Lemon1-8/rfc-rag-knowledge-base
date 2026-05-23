from fastapi import APIRouter, HTTPException
from app.schemas.document import DocumentListResponse, CrawlRequest
from app.core.vector_store import vector_store

router = APIRouter()


@router.get("/api/documents", response_model=DocumentListResponse)
async def list_documents():
    """文档列表。"""
    # 从 big collection 中获取所有文档
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
    # 暂时返回任务 ID（后续可接入 celery/background task）
    return {
        "task_id": f"task_{req.doc_type}_{hash(req.url) & 0xFFFF:04x}",
        "status": "accepted",
    }


@router.delete("/api/documents/{document_id}", status_code=204)
async def delete_document(document_id: str):
    """删除文档及其所有 chunk。"""
    try:
        vector_store.delete_by_document(document_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
