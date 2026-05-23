"""
爬虫模块：httpx 爬取 rfc-editor.org 的 RFC 文档（纯文本 .txt 格式）。

- 使用 Datatracker API 获取 RFC 列表
- 使用 rfc-editor.org/rfc/rfc{N}.txt 获取纯文本 RFC
"""

import re
from pathlib import Path

import httpx

DATATRACKER_API = "https://datatracker.ietf.org/api/v1/doc/document/"
RFC_TXT_BASE = "https://www.rfc-editor.org/rfc/"


async def fetch_rfc_list(
    client: httpx.AsyncClient,
    limit: int = 10,
    offset: int = 0,
) -> list[dict]:
    """通过 Datatracker API 获取 RFC 列表，按发布日期降序。"""
    params = {
        "format": "json",
        "type": "rfc",
        "limit": limit,
        "offset": offset,
        "sort": "-pub_date",
    }
    resp = await client.get(DATATRACKER_API, params=params, follow_redirects=True)
    resp.raise_for_status()
    data = resp.json()

    results = []
    for doc in data.get("objects", []):
        rfc_number = doc.get("rfc_number") or re.sub(
            r"^rfc", "", doc.get("name", ""), flags=re.IGNORECASE
        )
        results.append({
            "rfc_id": f"rfc{rfc_number}",
            "title": doc.get("title", f"RFC {rfc_number}"),
            "url": f"{RFC_TXT_BASE}rfc{rfc_number}.txt",
        })
    return results


async def fetch_rfc_text(client: httpx.AsyncClient, url: str) -> str:
    """爬取单篇 RFC 的纯文本。"""
    resp = await client.get(url, follow_redirects=True)
    resp.raise_for_status()
    return resp.text


async def crawl_top_rfcs(
    limit: int = 10,
    raw_dir: Path | None = None,
) -> list[dict]:
    """爬取前 N 篇 RFC 纯文本，保存到 raw_dir。"""
    async with httpx.AsyncClient(timeout=30.0) as client:
        items = await fetch_rfc_list(client, limit=limit)
        results = []

        for item in items:
            try:
                text = await fetch_rfc_text(client, item["url"])
                if raw_dir:
                    raw_path = raw_dir / f"{item['rfc_id']}.txt"
                    raw_path.write_text(text, encoding="utf-8")
                results.append({
                    "rfc_id": item["rfc_id"],
                    "title": item["title"],
                    "url": item["url"],
                    "text": text,
                })
            except Exception as e:
                results.append({
                    "rfc_id": item["rfc_id"],
                    "title": item["title"],
                    "url": item["url"],
                    "error": str(e),
                })

    return results
