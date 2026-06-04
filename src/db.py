"""SQLite — 게시 이력 + 답글 처리 기록 (중복 방지)."""
from __future__ import annotations

import sqlite3
import time
from contextlib import contextmanager
from typing import Iterator

from .config import DB_PATH


SCHEMA = """
CREATE TABLE IF NOT EXISTS posts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    threads_id TEXT UNIQUE,
    slot TEXT NOT NULL,            -- morning / noon / evening
    topic_key TEXT NOT NULL,       -- 어떤 토픽으로 썼는지 (중복 방지)
    text TEXT NOT NULL,
    image_url TEXT,
    created_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS replied (
    comment_id TEXT PRIMARY KEY,   -- 우리가 답한 원본 댓글의 id
    parent_post_id TEXT,
    reply_id TEXT,                  -- 우리 답글의 id
    replied_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS commented_external (
    -- 그로스 봇이 다른 사람 게시물에 단 댓글 기록 (중복/스팸 방지)
    target_post_id TEXT PRIMARY KEY,
    target_username TEXT,
    target_text_snippet TEXT,
    comment_id TEXT,
    keyword TEXT,
    commented_at INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_posts_topic ON posts(topic_key);
CREATE INDEX IF NOT EXISTS idx_posts_slot ON posts(slot);
CREATE INDEX IF NOT EXISTS idx_ext_user ON commented_external(target_username);
CREATE INDEX IF NOT EXISTS idx_ext_time ON commented_external(commented_at);
"""


@contextmanager
def conn() -> Iterator[sqlite3.Connection]:
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    try:
        yield c
        c.commit()
    finally:
        c.close()


def init() -> None:
    with conn() as c:
        c.executescript(SCHEMA)


def record_post(threads_id: str | None, slot: str, topic_key: str, text: str, image_url: str | None) -> None:
    with conn() as c:
        c.execute(
            "INSERT OR IGNORE INTO posts (threads_id, slot, topic_key, text, image_url, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (threads_id, slot, topic_key, text, image_url, int(time.time())),
        )


def recent_topic_keys(limit: int = 30) -> list[str]:
    with conn() as c:
        rows = c.execute(
            "SELECT topic_key FROM posts ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
    return [r["topic_key"] for r in rows]


def has_replied(comment_id: str) -> bool:
    with conn() as c:
        row = c.execute(
            "SELECT 1 FROM replied WHERE comment_id = ?", (comment_id,)
        ).fetchone()
    return row is not None


def record_reply(comment_id: str, parent_post_id: str | None, reply_id: str | None) -> None:
    with conn() as c:
        c.execute(
            "INSERT OR REPLACE INTO replied (comment_id, parent_post_id, reply_id, replied_at) "
            "VALUES (?, ?, ?, ?)",
            (comment_id, parent_post_id, reply_id, int(time.time())),
        )


def recent_post_ids(limit: int = 20) -> list[str]:
    with conn() as c:
        rows = c.execute(
            "SELECT threads_id FROM posts WHERE threads_id IS NOT NULL "
            "ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [r["threads_id"] for r in rows]


# ---------- 그로스 봇 ----------

def has_commented_external(target_post_id: str) -> bool:
    with conn() as c:
        row = c.execute(
            "SELECT 1 FROM commented_external WHERE target_post_id = ?", (target_post_id,)
        ).fetchone()
    return row is not None


def count_recent_external_comments(within_seconds: int) -> int:
    cutoff = int(time.time()) - within_seconds
    with conn() as c:
        row = c.execute(
            "SELECT COUNT(*) AS n FROM commented_external WHERE commented_at >= ?",
            (cutoff,),
        ).fetchone()
    return int(row["n"]) if row else 0


def count_external_comments_to_user(username: str, within_seconds: int) -> int:
    cutoff = int(time.time()) - within_seconds
    with conn() as c:
        row = c.execute(
            "SELECT COUNT(*) AS n FROM commented_external "
            "WHERE target_username = ? AND commented_at >= ?",
            (username, cutoff),
        ).fetchone()
    return int(row["n"]) if row else 0


def record_external_comment(
    target_post_id: str,
    target_username: str | None,
    target_text_snippet: str,
    comment_id: str | None,
    keyword: str,
) -> None:
    with conn() as c:
        c.execute(
            "INSERT OR REPLACE INTO commented_external "
            "(target_post_id, target_username, target_text_snippet, comment_id, keyword, commented_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (target_post_id, target_username, target_text_snippet[:200], comment_id, keyword, int(time.time())),
        )
