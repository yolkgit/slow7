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
    created_at INTEGER NOT NULL,
    -- 성과 지표 (track 스크립트가 주기적으로 갱신)
    views INTEGER DEFAULT 0,
    likes INTEGER DEFAULT 0,
    replies INTEGER DEFAULT 0,
    reposts INTEGER DEFAULT 0,
    quotes INTEGER DEFAULT 0,
    shares INTEGER DEFAULT 0,
    metrics_updated_at INTEGER DEFAULT 0
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

CREATE TABLE IF NOT EXISTS review_queue (
    -- 텔레그램 검수 대기 글
    wp_post_id TEXT PRIMARY KEY,    -- 워드프레스 글 ID
    topic_key TEXT,
    title TEXT,
    wp_link TEXT,
    content_html TEXT,              -- 현재 본문 (수정 시 갱신)
    status TEXT NOT NULL,           -- pending(검수대기) / published / skipped
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS kv (
    -- 잡다한 상태 저장 (텔레그램 last_update_id 등)
    k TEXT PRIMARY KEY,
    v TEXT
);

CREATE TABLE IF NOT EXISTS social_posts (
    -- SNS 크로스포스팅 추적 (한 글을 같은 플랫폼에 중복 게시 방지)
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    wp_post_id TEXT NOT NULL,
    platform TEXT NOT NULL,     -- x / facebook / threads / instagram
    sns_post_id TEXT,
    posted_at INTEGER NOT NULL,
    UNIQUE(wp_post_id, platform)
);

CREATE INDEX IF NOT EXISTS idx_posts_topic ON posts(topic_key);
CREATE INDEX IF NOT EXISTS idx_posts_slot ON posts(slot);
CREATE INDEX IF NOT EXISTS idx_ext_user ON commented_external(target_username);
CREATE INDEX IF NOT EXISTS idx_ext_time ON commented_external(commented_at);
CREATE INDEX IF NOT EXISTS idx_review_status ON review_queue(status);
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


_MIGRATION_COLUMNS = {
    "views": "INTEGER DEFAULT 0",
    "likes": "INTEGER DEFAULT 0",
    "replies": "INTEGER DEFAULT 0",
    "reposts": "INTEGER DEFAULT 0",
    "quotes": "INTEGER DEFAULT 0",
    "shares": "INTEGER DEFAULT 0",
    "metrics_updated_at": "INTEGER DEFAULT 0",
}


def init() -> None:
    with conn() as c:
        c.executescript(SCHEMA)
        # 기존 DB에 metrics 컬럼이 없으면 추가 (마이그레이션)
        existing = {row["name"] for row in c.execute("PRAGMA table_info(posts)").fetchall()}
        for col, decl in _MIGRATION_COLUMNS.items():
            if col not in existing:
                c.execute(f"ALTER TABLE posts ADD COLUMN {col} {decl}")


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


def recent_post_titles(limit: int = 12) -> list[str]:
    """최근 발행한 글 제목들 — 내용 차별화(중복 방지)에 사용."""
    with conn() as c:
        rows = c.execute(
            "SELECT text FROM posts WHERE slot='blog' AND text IS NOT NULL "
            "ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [r["text"] for r in rows if r["text"]]


def has_replied(comment_id: str) -> bool:
    with conn() as c:
        row = c.execute(
            "SELECT 1 FROM replied WHERE comment_id = ?", (comment_id,)
        ).fetchone()
    return row is not None


def is_our_reply(reply_id: str) -> bool:
    """이 ID가 우리(봇)가 직접 만든 답글의 ID인지 — 자기 답글에 또 답하지 않게."""
    with conn() as c:
        row = c.execute(
            "SELECT 1 FROM replied WHERE reply_id = ?", (reply_id,)
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


def posts_for_metrics(limit: int = 50) -> list[dict]:
    """metrics 갱신 대상 게시물 (threads_id 있는 것)."""
    with conn() as c:
        rows = c.execute(
            "SELECT threads_id, topic_key, slot, created_at FROM posts "
            "WHERE threads_id IS NOT NULL ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


def update_metrics(threads_id: str, m: dict) -> None:
    with conn() as c:
        c.execute(
            "UPDATE posts SET views=?, likes=?, replies=?, reposts=?, quotes=?, shares=?, "
            "metrics_updated_at=? WHERE threads_id=?",
            (
                m.get("views", 0), m.get("likes", 0), m.get("replies", 0),
                m.get("reposts", 0), m.get("quotes", 0), m.get("shares", 0),
                int(time.time()), threads_id,
            ),
        )


def _engagement_expr() -> str:
    # 가중 인게이지먼트 점수: 좋아요1 + 답글3 + 리포스트4 + 인용4 + 공유5 (+ 조회수 보정)
    return "(likes + replies*3 + reposts*4 + quotes*4 + shares*5)"


def topic_performance() -> list[dict]:
    """토픽별 평균 인게이지먼트 점수 (성과 기록 있는 것만)."""
    expr = _engagement_expr()
    with conn() as c:
        rows = c.execute(
            f"SELECT topic_key, COUNT(*) AS n, "
            f"AVG({expr}) AS avg_score, AVG(views) AS avg_views, "
            f"SUM(likes) AS likes, SUM(replies) AS replies "
            f"FROM posts WHERE metrics_updated_at > 0 "
            f"GROUP BY topic_key ORDER BY avg_score DESC",
        ).fetchall()
    return [dict(r) for r in rows]


def topic_scores() -> dict[str, float]:
    """토픽별 평균 점수 dict. 가중 선택에 사용."""
    return {r["topic_key"]: float(r["avg_score"] or 0) for r in topic_performance()}


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


# ---------- 검수 큐 (텔레그램) ----------

def add_review(wp_post_id: str, topic_key: str, title: str, wp_link: str, content_html: str) -> None:
    now = int(time.time())
    with conn() as c:
        c.execute(
            "INSERT OR REPLACE INTO review_queue "
            "(wp_post_id, topic_key, title, wp_link, content_html, status, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, 'pending', ?, ?)",
            (wp_post_id, topic_key, title, wp_link, content_html, now, now),
        )


def oldest_pending_review() -> dict | None:
    """가장 오래된 검수 대기 글 1개 (현재 활성 검수 대상)."""
    with conn() as c:
        row = c.execute(
            "SELECT * FROM review_queue WHERE status='pending' ORDER BY created_at ASC LIMIT 1"
        ).fetchone()
    return dict(row) if row else None


def pending_review_count() -> int:
    with conn() as c:
        row = c.execute("SELECT COUNT(*) AS n FROM review_queue WHERE status='pending'").fetchone()
    return int(row["n"]) if row else 0


def update_review_content(wp_post_id: str, content_html: str, title: str | None = None) -> None:
    with conn() as c:
        if title is not None:
            c.execute(
                "UPDATE review_queue SET content_html=?, title=?, updated_at=? WHERE wp_post_id=?",
                (content_html, title, int(time.time()), wp_post_id),
            )
        else:
            c.execute(
                "UPDATE review_queue SET content_html=?, updated_at=? WHERE wp_post_id=?",
                (content_html, int(time.time()), wp_post_id),
            )


def mark_review_status(wp_post_id: str, status: str) -> None:
    with conn() as c:
        c.execute(
            "UPDATE review_queue SET status=?, updated_at=? WHERE wp_post_id=?",
            (status, int(time.time()), wp_post_id),
        )


def published_blog_links(limit: int = 8, exclude_wp_id: str | None = None) -> list[dict]:
    """이미 발행(published)된 블로그 글의 (title, wp_link) 목록 — 내부 링크용."""
    with conn() as c:
        rows = c.execute(
            "SELECT wp_post_id, title, wp_link FROM review_queue "
            "WHERE status='published' AND wp_link IS NOT NULL AND wp_link != '' "
            "ORDER BY updated_at DESC LIMIT ?",
            (limit + 1,),
        ).fetchall()
    out = []
    for r in rows:
        if exclude_wp_id and str(r["wp_post_id"]) == str(exclude_wp_id):
            continue
        out.append({"title": r["title"], "link": r["wp_link"]})
        if len(out) >= limit:
            break
    return out


# ---------- KV 스토어 ----------

def kv_get(key: str, default: str | None = None) -> str | None:
    with conn() as c:
        row = c.execute("SELECT v FROM kv WHERE k=?", (key,)).fetchone()
    return row["v"] if row else default


def kv_set(key: str, value: str) -> None:
    with conn() as c:
        c.execute("INSERT OR REPLACE INTO kv (k, v) VALUES (?, ?)", (key, value))


# ---------- SNS 크로스포스팅 ----------

def already_posted_social(wp_post_id: str, platform: str) -> bool:
    with conn() as c:
        row = c.execute(
            "SELECT 1 FROM social_posts WHERE wp_post_id=? AND platform=?",
            (wp_post_id, platform),
        ).fetchone()
    return row is not None


def record_social_post(wp_post_id: str, platform: str, sns_post_id: str | None) -> None:
    with conn() as c:
        c.execute(
            "INSERT OR IGNORE INTO social_posts (wp_post_id, platform, sns_post_id, posted_at) "
            "VALUES (?, ?, ?, ?)",
            (wp_post_id, platform, sns_post_id, int(time.time())),
        )


def published_posts_for_promo(limit: int = 20) -> list[dict]:
    """SNS 홍보 대상 — 발행(published)된 블로그 글."""
    with conn() as c:
        rows = c.execute(
            "SELECT wp_post_id, title, wp_link, content_html, topic_key FROM review_queue "
            "WHERE status='published' AND wp_link IS NOT NULL "
            "ORDER BY updated_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


def find_related_published(cluster: str, topic_keys_in_cluster: list[str]) -> dict | None:
    """주제군에 속한 발행 블로그 글 중 가장 최근 것 (SNS 링크용).

    topic_keys_in_cluster: 그 주제군에 속하는 토픽 키 목록.
    없으면 아무 발행글이나 최근 것 반환.
    """
    with conn() as c:
        rows = c.execute(
            "SELECT wp_post_id, title, wp_link, topic_key FROM review_queue "
            "WHERE status='published' AND wp_link IS NOT NULL AND wp_link != '' "
            "ORDER BY updated_at DESC LIMIT 50"
        ).fetchall()
    posts = [dict(r) for r in rows]
    if not posts:
        return None
    # 같은 주제군 글 우선
    for p in posts:
        if p["topic_key"] in topic_keys_in_cluster:
            return p
    # 없으면 가장 최근 발행글
    return posts[0]
