import time
from fastapi import APIRouter, Query
from app.schemas.search import SearchResponse, SearchResult
from app.retrieval.hybrid_search import hybrid_search

router = APIRouter()


@router.get("/api/search", response_model=SearchResponse)
async def search(
    q: str = Query(..., description="搜索查询"),
    top_k: int = Query(default=5, ge=1, le=20),
):
    """直接检索接口（调试用）。"""
    start = time.time()
    results = await hybrid_search(q, top_k=top_k)
    elapsed = (time.time() - start) * 1000

    return SearchResponse(
        results=[
            SearchResult(
                document_id=r["document_id"],
                title=r["title"],
                section_path=r["section_path"],
                content_preview=r["content"][:200] if r["content"] else "",
                url=r["url"],
                score=r["score"],
            )
            for r in results
        ],
        query_time_ms=round(elapsed, 1),
    )
