from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.chat import router as chat_router
from app.api.search import router as search_router
from app.api.documents import router as documents_router
from app.api.conversations import router as conversations_router
from app.core.vector_store import vector_store
from app.core.sparse_search import sparse_retriever


@asynccontextmanager
async def lifespan(app: FastAPI):
    """启动时构建 BM25 索引。"""
    try:
        count = vector_store.count_small()
        if count > 0:
            sparse_retriever.build_index(vector_store)
    except Exception:
        pass  # BM25 索引构建失败不影响服务启动
    yield


app = FastAPI(title="RFC RAG Knowledge Base", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat_router)
app.include_router(search_router)
app.include_router(documents_router)
app.include_router(conversations_router)


@app.get("/api/health")
async def health():
    return {"status": "ok"}
