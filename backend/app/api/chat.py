import time
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from app.schemas.chat import ChatRequest
from app.retrieval.rag_chain import rag_query

router = APIRouter()


@router.post("/api/chat")
async def chat(req: ChatRequest):
    """流式对话接口（SSE）。"""
    start = time.time()

    async def event_stream():
        async for event in rag_query(req.query, req.top_k):
            yield event

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Query-Time-Ms": str(int((time.time() - start) * 1000)),
        },
    )
