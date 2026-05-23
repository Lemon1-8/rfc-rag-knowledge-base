from fastapi import APIRouter, HTTPException
from app.schemas.conversation import (
    ConversationListResponse,
    ConversationDetail,
    CreateConversationRequest,
)
from app.core import database as db

router = APIRouter()


@router.get("/api/conversations", response_model=ConversationListResponse)
async def list_conversations():
    convs = db.list_conversations()
    return ConversationListResponse(conversations=convs)


@router.post("/api/conversations", response_model=ConversationDetail, status_code=201)
async def create_conversation(req: CreateConversationRequest | None = None):
    title = req.title if req else "新对话"
    conv = db.create_conversation(title)
    return ConversationDetail(id=conv["id"], title=conv["title"],
                              created_at=conv["created_at"], updated_at=conv["updated_at"],
                              messages=[])


@router.get("/api/conversations/{conversation_id}", response_model=ConversationDetail)
async def get_conversation(conversation_id: str):
    conv = db.get_conversation(conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="对话不存在")
    return ConversationDetail(
        id=conv["id"], title=conv["title"],
        created_at=conv["created_at"], updated_at=conv["updated_at"],
        messages=conv.get("messages", []),
    )


@router.delete("/api/conversations/{conversation_id}", status_code=204)
async def delete_conversation(conversation_id: str):
    db.delete_conversation(conversation_id)
