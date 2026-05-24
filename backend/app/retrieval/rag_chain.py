"""
RAG 链：检索 → 构建 Prompt → LLM 流式生成。
支持多轮对话历史注入。
"""

import json
from typing import AsyncIterator

from app.retrieval.hybrid_search import hybrid_search
from app.core.llm import generate_stream

SYSTEM_PROMPT = """你是一个 RFC 技术文档专家助手。你会收到与用户问题相关的 RFC 文档片段，请基于这些片段回答问题。

核心规则：
1. 严格基于提供的文档内容回答，绝不编造信息或猜测
2. 每条关键信息标注来源编号，如 [1]、[2]
3. 如果多个来源对同一问题有不同描述，指出差异并分别引用
4. 如果文档内容不足以回答问题，诚实说明"现有资料中未找到相关信息"，不要猜测
5. 使用中文回答，专业术语保留英文原名并附简要解释
6. 回答结构：先给出直接结论，再展开详细解释，最后列出参考文献
7. 涉及协议参数（端口号、版本号、常量值）时，务必准确引用原文，不确定时宁可不说
8. 涉及算法或流程时，分步骤清晰说明，避免笼统概括"""

USER_PROMPT_TEMPLATE = """参考资料：

{context}

{history}

---

问题：{query}

请严格基于以上参考资料回答。对于参考资料中未覆盖的内容，请明确说明。"""


async def rag_query(
    query: str,
    top_k: int = 5,
    history: list[dict] | None = None,
) -> AsyncIterator[str]:
    """执行 RAG 查询，流式返回 SSE 事件。

    history: [{"role": "user/assistant", "content": "..."}]
    """
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

    # 构建历史对话文本
    history_text = ""
    if history:
        history_lines = ["\n## 历史对话\n"]
        for h in history:
            role_label = "用户" if h["role"] == "user" else "助手"
            history_lines.append(f"**{role_label}**：{h['content']}")
        history_text = "\n".join(history_lines)

    user_prompt = USER_PROMPT_TEMPLATE.format(
        context=context,
        history=history_text,
        query=query,
    )

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
