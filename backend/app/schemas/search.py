from pydantic import BaseModel


class SearchResult(BaseModel):
    document_id: str
    title: str
    section_path: str
    content_preview: str
    url: str
    score: float


class SearchResponse(BaseModel):
    results: list[SearchResult]
    query_time_ms: float
