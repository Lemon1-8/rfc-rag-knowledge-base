"""
RAG 链：检索 → 构建 Prompt → LLM 流式生成。
"""

import json
from typing import AsyncIterator

from app.retrieval.hybrid_search import hybrid_search
from app.core.llm import generate_stream

SYSTEM_PROMPT = """你是一个 RFC 技术文档助手。根据提供的 RFC 文档片段回答用户问题。

要求：
1. 基于提供的文档内容回答，不要编造信息
2. 引用来源时使用编号标注，如 [1]、[2]
3. 如果文档内容不足以回答问题，请诚实告知
4. 使用中文回答，专业术语保留英文原名"""

USER_PROMPT_TEMPLATE = """参考资料：

{context}

---

问题：{query}

请基于以上参考资料回答问题。"""


async def rag_query(query: str, top_k: int = 5) -> AsyncIterator[str]:
    """执行 RAG 查询，流式返回 token。"""
    # 检索
    results = await hybrid_search(query, top_k=top_k)

    # 构建上下文
    context_parts = []
    sources = []
    for i, r in enumerate(results):
        ref_id = i + 1
        context_parts.append(
            f"## [{ref_id}] {r['title']} - {r['section_path']}\n\n{r['content']}"
        )
        sources.append({
            "document_id": r["document_id"],
            "title": r["title"],
            "section": r["section_path"],
            "content_preview": r["content"][:200] if r["content"] else "",
            "url": r["url"],
            "score": r["score"],
        })

    context = "\n\n---\n\n".join(context_parts) if context_parts else "未找到相关文档。"
    user_prompt = USER_PROMPT_TEMPLATE.format(context=context, query=query)

    # SSE 事件：先发 sources
    yield f"data: {json.dumps({'type': 'sources', 'documents': sources}, ensure_ascii=False)}\n\n"

    # 流式 token
    try:
        async for token in generate_stream(SYSTEM_PROMPT, user_prompt):
            yield f"data: {json.dumps({'type': 'token', 'content': token}, ensure_ascii=False)}\n\n"
    except Exception as e:
        yield f"data: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"
        return

    yield f"data: {json.dumps({'type': 'done'})}\n\n"
