from pydantic import BaseModel, Field


class MessageOut(BaseModel):
    id: int
    role: str
    content: str
    sources: list = []
    created_at: str


class ConversationOut(BaseModel):
    id: str
    title: str
    created_at: str
    updated_at: str


class ConversationDetail(ConversationOut):
    messages: list[MessageOut] = []


class ConversationListResponse(BaseModel):
    conversations: list[ConversationOut]


class CreateConversationRequest(BaseModel):
    title: str = "新对话"
