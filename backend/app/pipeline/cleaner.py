"""
清洗器模块：RFC 纯文本 → Markdown，提取结构化章节信息。

RFC 纯文本标准格式：
- 页头（form feed + 页码）
- 标题、作者、摘要
- 目录
- 编号章节（如 "1. Introduction", "2.1. Subsection"）
- 参考文献
"""

import re
from pathlib import Path


def clean_rfc_text(text: str, rfc_id: str, url: str) -> dict:
    """将 RFC 纯文本清洗为 Markdown，提取章节结构。"""
    # 移除换页符
    text = text.replace("\f", "\n")

    # 移除页眉/页脚行（如 "[Page 5]" 或独立的页码）
    text = re.sub(r"\n\s*\[Page\s+\d+\]\s*\n", "\n", text)
    # 移除行尾的页码（格式：空白 + 数字）
    text = re.sub(r"\n\s{20,}\d+\s*\n", "\n", text)

    # 提取标题（第一个非空行通常是标题行）
    lines = text.strip().split("\n")
    title = rfc_id.upper()
    for line in lines[:20]:
        stripped = line.strip()
        if stripped and not re.match(r"^(Network Working Group|Request for Comments|Internet|ISSN|Category|Obsoletes|Updates|RFC \d)", stripped):
            if len(stripped) > 3:
                title = stripped
                break

    # 提取章节
    sections = _extract_rfc_sections(text, rfc_id, url)

    # 生成 Markdown
    markdown = _text_to_markdown(text, title, url)

    return {
        "rfc_id": rfc_id,
        "title": title,
        "url": url.replace(".txt", ".html"),
        "markdown": markdown,
        "sections": sections,
    }


_SECTION_RE = re.compile(
    r"^(\d+(?:\.\d+)*)\s+\.?\s*(.+)$",
    re.MULTILINE,
)
_APPENDIX_RE = re.compile(
    r"^(Appendix\s+[A-Z])\.?\s*(.*)$",
    re.MULTILINE,
)
_REFERENCES_RE = re.compile(
    r"^(Normative References|Informative References|References)\s*$",
    re.IGNORECASE | re.MULTILINE,
)


def _extract_rfc_sections(text: str, rfc_id: str, url: str) -> list[dict]:
    """从 RFC 纯文本中提取章节结构。"""
    html_url = url.replace(".txt", ".html")
    sections: list[dict] = []
    current_section: dict | None = None
    content_lines: list[str] = []

    def flush():
        nonlocal current_section, content_lines
        if current_section and content_lines:
            body = "\n".join(content_lines)
            if body.strip():
                current_section["content_md"] = body
                sections.append(current_section)
        content_lines = []
        current_section = None

    for line in text.split("\n"):
        stripped = line.strip()

        # 检查是否为节标题
        m = _SECTION_RE.match(stripped)
        if not m:
            m = _APPENDIX_RE.match(stripped)
        if not m:
            m_ref = _REFERENCES_RE.match(stripped)

        if m:
            flush()
            current_section = {
                "heading": stripped,
                "level": 2,  # 统一作为 h2 级别
                "url": html_url,
                "content_md": "",
            }
            content_lines = []
        elif m_ref:
            flush()
            current_section = {
                "heading": stripped,
                "level": 2,
                "url": html_url,
                "content_md": "",
            }
            content_lines = [stripped]
        elif current_section is not None:
            content_lines.append(stripped)
        elif stripped:
            # 前导内容（摘要、介绍性文字，在第一个正式章节之前）
            if not any(
                kw in stripped.lower()
                for kw in ["network working group", "request for comments:", "rfc " + rfc_id[3:], "internet engineering"]
            ):
                content_lines.append(stripped)

    flush()

    # 如果没有解析到章节，创建单个文档 section
    if not sections:
        sections = [{
            "heading": "Full Document",
            "level": 1,
            "url": html_url,
            "content_md": text,
        }]

    return sections


def _text_to_markdown(text: str, title: str, url: str) -> str:
    """将 RFC 纯文本转换为整洁的 Markdown。"""
    html_url = url.replace(".txt", ".html")
    lines = [f"# {title}\n", f"> 来源: {html_url}\n"]

    # 跳过 RFC 标准头部
    in_body = False
    for line in text.split("\n"):
        stripped = line.strip()
        if not in_body:
            # RFC 正文通常从 "Abstract" 或第一个编号章节开始
            if re.match(r"^(Abstract|Status of This Memo|1\.\s)", stripped, re.IGNORECASE):
                in_body = True
            else:
                continue

        # 跳过换页标记和页眉
        if re.match(r"^\f", line) or re.match(r"^\s*\d+\s*$", stripped):
            continue
        # 跳过 RFC 页脚
        if re.match(r"^[A-Z][a-z]+\s+.*\[Page\s+\d+\]$", stripped):
            continue
        if re.match(r"^RFC\s+\d+\s+.*\d{4}$", stripped):
            continue

        lines.append(stripped)

    return "\n".join(lines)


def save_processed(cleaned: dict, processed_dir: Path) -> Path:
    """将清洗后的 Markdown 保存到 processed 目录。"""
    path = processed_dir / f"{cleaned['rfc_id']}.md"
    path.write_text(cleaned["markdown"], encoding="utf-8")
    return path
