from datetime import datetime
from pydantic import BaseModel, Field


class DocumentInfo(BaseModel):
    id: str
    title: str
    source_url: str
    chunk_count: int = 0
    indexed_at: datetime | None = None
    status: str = "unknown"


class DocumentListResponse(BaseModel):
    documents: list[DocumentInfo]
    total: int


class CrawlRequest(BaseModel):
    url: str = Field(..., description="RFC URL")
    doc_type: str = Field(default="rfc")
