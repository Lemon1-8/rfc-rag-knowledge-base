from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    query: str = Field(..., description="用户问题")
    conversation_id: str | None = Field(default=None, description="对话 ID，为空则创建新对话")
    top_k: int = Field(default=5, ge=1, le=20, description="检索文档数")


class Source(BaseModel):
    document_id: str
    title: str
    section: str
    content_preview: str
    url: str
    score: float
