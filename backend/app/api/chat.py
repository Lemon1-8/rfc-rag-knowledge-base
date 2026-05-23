import json
import time
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from app.schemas.chat import ChatRequest
from app.retrieval.rag_chain import rag_query
from app.core import database as db

router = APIRouter()


@router.post("/api/chat")
async def chat(req: ChatRequest):
    start = time.time()

    # 自动创建对话
    conv_id = req.conversation_id
    if not conv_id:
        conv = db.create_conversation(title=req.query[:30])
        conv_id = conv["id"]
    else:
        existing = db.get_conversation(conv_id)
        if not existing:
            conv = db.create_conversation(title=req.query[:30])
            conv_id = conv["id"]

    # 保存用户消息
    db.add_message(conv_id, "user", req.query)

    # 获取历史消息（用于多轮对话上下文）
    history = db.get_messages(conv_id)
    history_for_llm = [
        {"role": m["role"], "content": m["content"]}
        for m in history[:-1]  # 排除刚存的用户消息，由 rag_query 自己加入
    ]

    async def event_stream():
        full_response = ""
        all_sources = []

        async for event in rag_query(req.query, req.top_k, history_for_llm):
            # 抽取出 sources 事件中的数据
            if "sources" in event:
                try:
                    data = json.loads(event.removeprefix("data: ").strip())
                    if data.get("type") == "sources":
                        all_sources = data.get("documents", [])
                except Exception:
                    pass
            yield event

            # 累积 token
            try:
                data = json.loads(event.removeprefix("data: ").strip())
                if data.get("type") == "token":
                    full_response += data.get("content", "")
            except Exception:
                pass

        # 保存助手消息
        db.add_message(conv_id, "assistant", full_response, all_sources)

        # 自动更新对话标题（首次对话后用第一个问题做标题）
        history_count = len(db.get_messages(conv_id))
        if history_count <= 2:  # 只有刚存的 user + assistant 两条
            db.update_conversation_title(conv_id, req.query[:40])

        # 追加 conversation_id 事件
        yield f"data: {json.dumps({'type': 'conversation_id', 'conversation_id': conv_id}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Query-Time-Ms": str(int((time.time() - start) * 1000)),
        },
    )
