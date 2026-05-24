"""
DeepSeek-V3 客户端 —— 使用 LangChain ChatOpenAI 兼容 OpenAI 接口。
"""

from typing import AsyncIterator

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

from app.config import settings


def build_llm(streaming: bool = True) -> ChatOpenAI:
    return ChatOpenAI(
        model=settings.deepseek_model,
        openai_api_key=settings.deepseek_api_key,
        base_url=settings.deepseek_base_url,
        temperature=settings.llm_temperature,
        max_tokens=settings.llm_max_tokens,
        streaming=streaming,
    )


async def generate_stream(
    system_prompt: str,
    user_prompt: str,
) -> AsyncIterator[str]:
    """流式生成，逐 token yield。"""
    llm = build_llm(streaming=True)
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt),
    ]
    async for chunk in llm.astream(messages):
        content = chunk.content
        if content:
            yield content
