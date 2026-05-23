from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.chat import router as chat_router
from app.api.search import router as search_router
from app.api.documents import router as documents_router

app = FastAPI(title="RFC RAG Knowledge Base", version="0.1.0")

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


@app.get("/api/health")
async def health():
    return {"status": "ok"}
