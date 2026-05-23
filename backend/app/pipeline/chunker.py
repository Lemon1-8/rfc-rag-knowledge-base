"""
智能切片器：Small-to-Big + 按内容类型分治。

- 小 chunk（≤500 字符）：检索用，送入 Embedding 做语义匹配
- 大 chunk（完整 section）：命中后，完整 section 喂给 LLM

四种内容类型：
- TERM_DEF: 术语定义
- CODE_BLOCK: ABNF 语法 / 代码块 / ASCII 图表
- LIST: 列表（bullet/numbered）
- NARRATIVE: 普通叙述
"""

import hashlib
import re
from dataclasses import dataclass, field
from enum import Enum

from langchain_text_splitters import RecursiveCharacterTextSplitter


class ContentType(str, Enum):
    TERM_DEF = "term_def"
    CODE_BLOCK = "code_block"
    LIST = "list"
    NARRATIVE = "narrative"


@dataclass
class SmallChunk:
    chunk_id: str
    parent_chunk_id: str
    content: str
    content_type: ContentType
    section_path: str
    url: str
    content_hash: str


@dataclass
class BigChunk:
    chunk_id: str
    document_id: str
    title: str
    section_path: str
    content: str
    url: str
    small_chunk_ids: list[str] = field(default_factory=list)


def _hash_text(text: str) -> str:
    return hashlib.md5(text.encode("utf-8")).hexdigest()


def _classify_line(line: str) -> ContentType:
    """分类单行文本的内容类型。"""
    stripped = line.strip()
    if not stripped:
        return ContentType.NARRATIVE

    # 术语定义
    if re.match(
        r'^(A|An|The)\s+\w+.*\b(is|are|denotes|refers to|means)\b',
        stripped,
        re.IGNORECASE,
    ):
        return ContentType.TERM_DEF

    # 代码块 / ABNF / ASCII 图表（含大量特殊字符）
    code_indicators = ["::=", "---", "===", "+++", "| ", "+-", "->", "=>"]
    if any(ind in stripped for ind in code_indicators):
        return ContentType.CODE_BLOCK
    # 纯 ASCII 图表行
    if re.match(r'^[\s\|+\-\=\>\<]+$', stripped):
        return ContentType.CODE_BLOCK

    # 列表
    if re.match(r'^(\s*[-*+]\s|\s*\d+[\.\)]\s|\s*[a-zA-Z][\.\)]\s)', stripped):
        return ContentType.LIST

    return ContentType.NARRATIVE


def _classify_paragraph(paragraph: str) -> ContentType:
    """分类整个段落的内容类型。"""
    lines = paragraph.strip().split("\n")
    types = [_classify_line(l) for l in lines if l.strip()]

    # 如果有任何代码行，整个段落标记为代码块
    if ContentType.CODE_BLOCK in types:
        return ContentType.CODE_BLOCK
    # 如果大部分是列表行
    if types.count(ContentType.LIST) > len(types) * 0.5:
        return ContentType.LIST
    # 如果开头是术语定义
    if types and types[0] == ContentType.TERM_DEF:
        return ContentType.TERM_DEF
    return ContentType.NARRATIVE


def _build_small_chunks(
    paragraphs: list[tuple[str, ContentType, str, str]],
    parent_chunk_id: str,
    rfc_id: str,
    max_size: int = 500,
) -> list[SmallChunk]:
    """从段落列表组装小 chunk。同类型邻近合并，不超过 max_size。"""
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=max_size,
        chunk_overlap=50,
        separators=["\n\n", "\n", ". ", " ", ""],
    )

    chunks: list[SmallChunk] = []
    buffer: list[tuple[str, ContentType, str, str]] = []
    buffer_len = 0

    def flush():
        nonlocal buffer, buffer_len
        if not buffer:
            return None
        merged = "\n".join(p[0] for p in buffer)
        ctype = buffer[0][1]
        section_path = buffer[0][2]
        section_url = buffer[0][3]
        prefix = f"[{section_path}]\n" if section_path else ""
        chunk = SmallChunk(
            chunk_id=f"{rfc_id}_{_hash_text(merged)[:8]}",
            parent_chunk_id=parent_chunk_id,
            content=prefix + merged,
            content_type=ctype,
            section_path=section_path,
            url=section_url,
            content_hash=_hash_text(merged),
        )
        buffer, buffer_len = [], 0
        return chunk

    for para_text, ctype, sec_path, sec_url in paragraphs:
        # 跨内容类型时 flush
        if buffer and ctype != buffer[-1][1]:
            if c := flush():
                chunks.append(c)

        if buffer_len + len(para_text) <= max_size:
            buffer.append((para_text, ctype, sec_path, sec_url))
            buffer_len += len(para_text)
        else:
            if c := flush():
                chunks.append(c)
            if len(para_text) > max_size:
                sub_texts = text_splitter.split_text(para_text)
                for sub in sub_texts:
                    prefix = f"[{sec_path}]\n" if sec_path else ""
                    chunks.append(SmallChunk(
                        chunk_id=f"{rfc_id}_{_hash_text(sub)[:8]}",
                        parent_chunk_id=parent_chunk_id,
                        content=prefix + sub,
                        content_type=ctype,
                        section_path=sec_path,
                        url=sec_url,
                        content_hash=_hash_text(sub),
                    ))
            else:
                buffer, buffer_len = [(para_text, ctype, sec_path, sec_url)], len(para_text)

    if c := flush():
        chunks.append(c)

    return chunks


def chunk_cleaned_md(
    markdown_text: str,
    rfc_id: str,
    title: str,
    url: str,
    sections: list[dict],
) -> tuple[list[BigChunk], list[SmallChunk]]:
    """主入口：将清洗后的 Markdown + sections 切分为 BigChunk 和 SmallChunk。"""
    big_chunks: list[BigChunk] = []
    small_chunks: list[SmallChunk] = []

    for i, sec in enumerate(sections):
        content = sec.get("content_md", "")
        heading = sec.get("heading", "")
        sec_url = sec.get("url", url)

        # 跳过太短的内容（如纯标题行）
        text_content = re.sub(r'^#+\s+.*$', '', content, flags=re.MULTILINE).strip()
        if len(text_content) < 20:
            continue

        big_id = f"{rfc_id}_sec{i}"
        big = BigChunk(
            chunk_id=big_id,
            document_id=rfc_id,
            title=title,
            section_path=heading,
            content=content,
            url=sec_url,
        )

        # 按段落分割并分类
        paragraphs = _split_paragraphs(content, heading, sec_url)
        smalls = _build_small_chunks(paragraphs, big_id, rfc_id)
        big.small_chunk_ids = [s.chunk_id for s in smalls]

        big_chunks.append(big)
        small_chunks.extend(smalls)

    return big_chunks, small_chunks


def _split_paragraphs(
    text: str,
    section_path: str,
    section_url: str,
) -> list[tuple[str, ContentType, str, str]]:
    """将文本按空行分割为段落，并分类。"""
    # 按空行分割
    raw_paras = re.split(r"\n\s*\n", text)
    results = []
    for para in raw_paras:
        para = para.strip()
        if not para:
            continue
        ctype = _classify_paragraph(para)
        results.append((para, ctype, section_path, section_url))
    return results
