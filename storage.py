from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any

from config import DATA_DIR, DB_PATH
from utils import now_iso

ANALYSES_SCHEMA = """
CREATE TABLE analyses (
    event_id TEXT PRIMARY KEY,
    ticker TEXT NOT NULL,
    event_type TEXT NOT NULL,
    generated_by TEXT NOT NULL,
    summary TEXT NOT NULL,
    disclaimer TEXT NOT NULL,
    analysis_json TEXT NOT NULL,
    detected_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""

SOURCES_SCHEMA = """
CREATE TABLE sources (
    event_id TEXT NOT NULL,
    source_id INTEGER NOT NULL,
    source_type TEXT NOT NULL,
    title TEXT NOT NULL,
    url TEXT NOT NULL,
    publisher TEXT NOT NULL,
    published_at TEXT,
    excerpt TEXT NOT NULL,
    source_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (event_id, source_id)
);
"""

USERS_SCHEMA = """
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    last_login_at TEXT
);
"""

SESSIONS_SCHEMA = """
CREATE TABLE sessions (
    token_hash TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL
);
"""

EXPECTED_COLUMNS = {
    "analyses": {
        "event_id",
        "ticker",
        "event_type",
        "generated_by",
        "summary",
        "disclaimer",
        "analysis_json",
        "detected_at",
        "created_at",
        "updated_at",
    },
    "sources": {
        "event_id",
        "source_id",
        "source_type",
        "title",
        "url",
        "publisher",
        "published_at",
        "excerpt",
        "source_json",
        "created_at",
        "updated_at",
    },
    "users": {
        "id",
        "email",
        "password_hash",
        "created_at",
        "updated_at",
        "last_login_at",
    },
    "sessions": {
        "token_hash",
        "user_id",
        "created_at",
        "expires_at",
    },
}


def get_connection(db_path: Path = DB_PATH) -> sqlite3.Connection:
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    return connection


def _table_columns(connection: sqlite3.Connection, table_name: str) -> set[str]:
    rows = connection.execute(f"PRAGMA table_info({table_name})").fetchall()
    return {row[1] for row in rows}


def _ensure_table_schema(connection: sqlite3.Connection, table_name: str, schema_sql: str) -> None:
    columns = _table_columns(connection, table_name)
    if not columns:
        connection.execute(schema_sql)
        return
    if columns != EXPECTED_COLUMNS[table_name]:
        connection.execute(f"DROP TABLE IF EXISTS {table_name}")
        connection.execute(schema_sql)


def init_db(db_path: Path = DB_PATH) -> None:
    DATA_DIR.mkdir(exist_ok=True)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with closing(get_connection(db_path)) as connection:
        _ensure_table_schema(connection, "analyses", ANALYSES_SCHEMA)
        _ensure_table_schema(connection, "sources", SOURCES_SCHEMA)
        _ensure_table_schema(connection, "users", USERS_SCHEMA)
        _ensure_table_schema(connection, "sessions", SESSIONS_SCHEMA)
        connection.execute("CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id)")
        connection.commit()


def save_briefing_snapshot(payload: dict[str, Any], db_path: Path = DB_PATH) -> None:
    event = payload.get("event") or {}
    stock = payload.get("stock") or {}
    analysis = payload.get("analysis") or {}
    sources = payload.get("sources") or []
    event_id = str(event.get("id") or "").strip()
    if not event_id:
        return

    timestamp = now_iso()
    analysis_json = json.dumps(analysis, ensure_ascii=False)

    with closing(get_connection(db_path)) as connection:
        connection.execute(
            """
            INSERT INTO analyses (
                event_id, ticker, event_type, generated_by, summary, disclaimer,
                analysis_json, detected_at, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(event_id) DO UPDATE SET
                ticker=excluded.ticker,
                event_type=excluded.event_type,
                generated_by=excluded.generated_by,
                summary=excluded.summary,
                disclaimer=excluded.disclaimer,
                analysis_json=excluded.analysis_json,
                detected_at=excluded.detected_at,
                updated_at=excluded.updated_at
            """,
            (
                event_id,
                stock.get("ticker", ""),
                event.get("event_type", ""),
                analysis.get("generated_by", "unknown"),
                analysis.get("summary", ""),
                analysis.get("disclaimer", ""),
                analysis_json,
                event.get("detected_at"),
                timestamp,
                timestamp,
            ),
        )

        for source in sources:
            source_json = json.dumps(source, ensure_ascii=False)
            connection.execute(
                """
                INSERT INTO sources (
                    event_id, source_id, source_type, title, url, publisher,
                    published_at, excerpt, source_json, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(event_id, source_id) DO UPDATE SET
                    source_type=excluded.source_type,
                    title=excluded.title,
                    url=excluded.url,
                    publisher=excluded.publisher,
                    published_at=excluded.published_at,
                    excerpt=excluded.excerpt,
                    source_json=excluded.source_json,
                    updated_at=excluded.updated_at
                """,
                (
                    event_id,
                    int(source.get("id", 0) or 0),
                    source.get("source_type", ""),
                    source.get("title", ""),
                    source.get("url", ""),
                    source.get("publisher", ""),
                    source.get("published_at"),
                    source.get("excerpt", ""),
                    source_json,
                    timestamp,
                    timestamp,
                ),
            )
        connection.commit()


def fetch_analysis_record(event_id: str, db_path: Path = DB_PATH) -> dict[str, Any] | None:
    with closing(get_connection(db_path)) as connection:
        row = connection.execute(
            "SELECT event_id, ticker, event_type, generated_by, summary, disclaimer, analysis_json, detected_at, created_at, updated_at FROM analyses WHERE event_id = ?",
            (event_id,),
        ).fetchone()
    return dict(row) if row else None
