from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DB_PATH = PROJECT_ROOT / "storage" / "chat_history.sqlite3"
DEFAULT_CONVERSATION_TITLE = "Cuộc trò chuyện mới"
LEGACY_DEFAULT_TITLES = (
    "Cuoc tro chuyen moi",
    "cuoc tro chuyen moi",
    "Cuộc trò chuyện mới",
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                sources_json TEXT NOT NULL DEFAULT '[]',
                meta_json TEXT NOT NULL DEFAULT '{}',
                error TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (conversation_id)
                    REFERENCES conversations(id)
                    ON DELETE CASCADE
            )
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_messages_conversation
            ON messages(conversation_id, id)
            """
        )
        conn.execute(
            """
            UPDATE conversations
            SET title = ?
            WHERE lower(trim(title)) IN (?, ?)
            """,
            (DEFAULT_CONVERSATION_TITLE, "cuoc tro chuyen moi", "cuộc trò chuyện mới"),
        )
        rows = conn.execute("SELECT id, title FROM conversations").fetchall()
        for row in rows:
            normalized_title = normalize_title(row["title"])
            if normalized_title != row["title"]:
                conn.execute(
                    "UPDATE conversations SET title = ? WHERE id = ?",
                    (normalized_title, row["id"]),
                )


def normalize_title(title: str | None) -> str:
    normalized = " ".join(str(title or "").split())
    if not normalized:
        return DEFAULT_CONVERSATION_TITLE
    if normalized.lower() in {item.lower() for item in LEGACY_DEFAULT_TITLES}:
        return DEFAULT_CONVERSATION_TITLE
    return normalized


def make_title(prompt: str, max_length: int = 56) -> str:
    title = normalize_title(prompt)
    if not title:
        return DEFAULT_CONVERSATION_TITLE
    if len(title) <= max_length:
        return title
    return title[: max_length - 3].rstrip() + "..."


def create_conversation(title: str = DEFAULT_CONVERSATION_TITLE) -> str:
    conversation_id = str(uuid.uuid4())
    created_at = _now()
    title = make_title(title)
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO conversations (id, title, created_at, updated_at)
            VALUES (?, ?, ?, ?)
            """,
            (conversation_id, title, created_at, created_at),
        )
    return conversation_id


def list_conversations(limit: int = 30) -> list[dict[str, Any]]:
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT id, title, created_at, updated_at
            FROM conversations
            ORDER BY updated_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    conversations: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        item["title"] = normalize_title(item.get("title"))
        conversations.append(item)
    return conversations


def message_count(conversation_id: str) -> int:
    with _connect() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS total FROM messages WHERE conversation_id = ?",
            (conversation_id,),
        ).fetchone()
    return int(row["total"] if row else 0)


def rename_conversation(conversation_id: str, title: str) -> None:
    with _connect() as conn:
        conn.execute(
            """
            UPDATE conversations
            SET title = ?, updated_at = ?
            WHERE id = ?
            """,
            (make_title(title), _now(), conversation_id),
        )


def delete_conversation(conversation_id: str) -> None:
    with _connect() as conn:
        conn.execute("DELETE FROM conversations WHERE id = ?", (conversation_id,))


def get_messages(conversation_id: str) -> list[dict[str, Any]]:
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT role, content, sources_json, meta_json, error, created_at
            FROM messages
            WHERE conversation_id = ?
            ORDER BY id ASC
            """,
            (conversation_id,),
        ).fetchall()

    messages: list[dict[str, Any]] = []
    for row in rows:
        messages.append(
            {
                "role": row["role"],
                "content": row["content"],
                "sources": json.loads(row["sources_json"] or "[]"),
                "meta": json.loads(row["meta_json"] or "{}"),
                "error": row["error"],
                "created_at": row["created_at"],
            }
        )
    return messages


def add_message(conversation_id: str, message: dict[str, Any]) -> None:
    created_at = _now()
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO messages (
                conversation_id,
                role,
                content,
                sources_json,
                meta_json,
                error,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                conversation_id,
                message.get("role") or "assistant",
                message.get("content") or "",
                json.dumps(message.get("sources") or [], ensure_ascii=False),
                json.dumps(message.get("meta") or {}, ensure_ascii=False),
                message.get("error"),
                created_at,
            ),
        )
        conn.execute(
            """
            UPDATE conversations
            SET updated_at = ?
            WHERE id = ?
            """,
            (created_at, conversation_id),
        )
