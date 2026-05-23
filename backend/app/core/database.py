"""
SQLite 数据库：存储对话和消息。
"""

import json
import sqlite3
import time
from pathlib import Path

DB_DIR = Path(__file__).parent.parent.parent / "data"
DB_PATH = DB_DIR / "conversations.db"


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime())


def get_db() -> sqlite3.Connection:
    DB_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    _ensure_tables(conn)
    return conn


def _ensure_tables(conn: sqlite3.Connection):
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS conversations (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL DEFAULT '新对话',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('user', 'assistant')),
            content TEXT NOT NULL DEFAULT '',
            sources TEXT DEFAULT '[]',
            created_at TEXT NOT NULL,
            FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_msg_conv ON messages(conversation_id, id);
    """)
    conn.commit()


# --- Conversation CRUD ---

def list_conversations() -> list[dict]:
    db = get_db()
    rows = db.execute(
        "SELECT id, title, created_at, updated_at FROM conversations ORDER BY updated_at DESC"
    ).fetchall()
    return [dict(r) for r in rows]


def create_conversation(title: str = "新对话") -> dict:
    db = get_db()
    conv_id = str(int(time.time() * 1_000_000))
    now = _now()
    db.execute(
        "INSERT INTO conversations (id, title, created_at, updated_at) VALUES (?, ?, ?, ?)",
        (conv_id, title, now, now),
    )
    db.commit()
    return {"id": conv_id, "title": title, "created_at": now, "updated_at": now}


def get_conversation(conv_id: str) -> dict | None:
    db = get_db()
    row = db.execute("SELECT id, title, created_at, updated_at FROM conversations WHERE id = ?", (conv_id,)).fetchone()
    if not row:
        return None
    result = dict(row)
    msgs = db.execute(
        "SELECT id, role, content, sources, created_at FROM messages WHERE conversation_id = ? ORDER BY id",
        (conv_id,),
    ).fetchall()
    result["messages"] = [
        {**dict(m), "sources": _parse_sources(m["sources"])} for m in msgs
    ]
    return result


def delete_conversation(conv_id: str):
    db = get_db()
    db.execute("DELETE FROM conversations WHERE id = ?", (conv_id,))
    db.commit()


def update_conversation_title(conv_id: str, title: str):
    db = get_db()
    db.execute(
        "UPDATE conversations SET title = ?, updated_at = ? WHERE id = ?",
        (title, _now(), conv_id),
    )
    db.commit()


# --- Message CRUD ---

def add_message(conv_id: str, role: str, content: str, sources: list | None = None) -> dict:
    db = get_db()
    now = _now()
    sources_json = json.dumps(sources or [], ensure_ascii=False)
    cur = db.execute(
        "INSERT INTO messages (conversation_id, role, content, sources, created_at) VALUES (?, ?, ?, ?, ?)",
        (conv_id, role, content, sources_json, now),
    )
    db.execute(
        "UPDATE conversations SET updated_at = ? WHERE id = ?",
        (now, conv_id),
    )
    db.commit()
    return {"id": cur.lastrowid, "role": role, "content": content, "sources": sources or [], "created_at": now}


def get_messages(conv_id: str) -> list[dict]:
    db = get_db()
    rows = db.execute(
        "SELECT id, role, content, sources, created_at FROM messages WHERE conversation_id = ? ORDER BY id",
        (conv_id,),
    ).fetchall()
    return [{**dict(r), "sources": _parse_sources(r["sources"])} for r in rows]


def _parse_sources(raw: str) -> list:
    try:
        return json.loads(raw) if raw else []
    except Exception:
        return []
