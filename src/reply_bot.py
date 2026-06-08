"""최근 내 게시물의 댓글을 폴링해 미답글에 자동 응답.

[안전장치]
- 본인 답글(봇/수동 모두)에 절대 또 답하지 않는 다중 self-check
- 한 사이클당 최대 N개만 답글 (자연스러움 + API 한도 보호)
- 답글 사이 5~30초 랜덤 딜레이 (사람처럼 보이기)
- 남은 댓글은 다음 사이클(15분 후)에 처리
"""
from __future__ import annotations

import random
import time

from . import config, db, threads_client, writer


# 한 사이클당 최대 답글 수 — 봇 티 줄이기 + 자연스러움
MAX_REPLIES_PER_RUN = 3
# 답글 사이 랜덤 딜레이 (초)
REPLY_DELAY_MIN = 5
REPLY_DELAY_MAX = 30


# 본인 username 캐시 (self-check용)
_MY_USERNAME: str | None = None


def _my_username() -> str:
    """본인 Threads username 한 번만 가져와 캐싱. 소문자."""
    global _MY_USERNAME
    if _MY_USERNAME is None:
        try:
            me = threads_client.me()
            _MY_USERNAME = (me.get("username") or "").lower()
            print(f"[reply_bot] 본인 username: @{_MY_USERNAME}")
        except Exception as e:
            print(f"[reply_bot] me() 실패 — username 캐시 못함: {e}")
            _MY_USERNAME = ""
    return _MY_USERNAME


def _is_mine(c: dict, my_id: str, my_username: str) -> tuple[bool, str]:
    """이 답글이 본인 것인지 다중 안전망으로 판단. (yes, reason)."""
    cid = c.get("id", "")

    # 1. DB에서 우리 봇이 만든 답글 ID인지
    if cid and db.is_our_reply(cid):
        return True, "our reply (db)"

    # 2. username 기반 (가장 견고)
    c_username = (c.get("username") or (c.get("from") or {}).get("username") or "").lower()
    if c_username and my_username and c_username == my_username:
        return True, f"self (username @{c_username})"

    # 3. from.id 기반 (보조 — 안 올 때 많음)
    from_user = (c.get("from") or {}).get("id") or c.get("user_id") or ""
    if from_user and str(from_user) == str(my_id):
        return True, f"self (id {from_user})"

    return False, ""


def run(max_posts: int = 10, dry_run: bool | None = None) -> int:
    """답글을 단 개수를 반환."""
    if dry_run is None:
        dry_run = config.DRY_RUN
    if not config.AUTO_REPLY_ENABLED:
        print("[reply_bot] AUTO_REPLY_ENABLED=false → skip")
        return 0

    db.init()
    my_id = config.THREADS_USER_ID
    my_username = _my_username()  # 캐시 워밍업

    # 본인 메인 게시물 + 본인이 단 답글 둘 다 추적
    # → 다른 사람 글에 단 내 답글에 누가 응답해도 자동 답글 가능
    main_posts = threads_client.fetch_user_posts(limit=max_posts)
    my_replies = threads_client.fetch_user_replies(limit=max_posts * 2)
    # 중복 제거 (id 기준)
    seen_ids = set()
    threads_to_track: list[dict] = []
    for t in main_posts + my_replies:
        tid = t.get("id")
        if tid and tid not in seen_ids:
            seen_ids.add(tid)
            threads_to_track.append(t)
    print(
        f"[reply_bot] 추적 대상: 메인 {len(main_posts)}개 + 답글 {len(my_replies)}개 "
        f"= 합계 {len(threads_to_track)}개 (중복 제거)"
    )

    replied = 0
    skipped_self = 0
    skipped_queue = 0  # 한도 초과로 못한 미답글 수 (모니터링용)
    reached_limit = False

    for post in threads_to_track:
        post_id = post["id"]
        post_text = post.get("text", "")
        try:
            conv = threads_client.fetch_conversation(post_id)
        except threads_client.ThreadsError as e:
            print(f"[reply_bot] fetch_conversation 실패 ({post_id}): {e}")
            continue

        for c in conv:
            cid = c.get("id")
            if not cid:
                continue

            # ⭐ 본인 답글 다중 self-check (가장 중요)
            is_mine, reason = _is_mine(c, my_id, my_username)
            if is_mine:
                skipped_self += 1
                continue

            if db.has_replied(cid):
                continue
            comment_text = (c.get("text") or "").strip()
            if not comment_text:
                continue
            username = c.get("username") or (c.get("from") or {}).get("username")

            # 사이클당 한도 도달 시 — 처리는 멈추되 남은 큐 카운트
            if replied >= MAX_REPLIES_PER_RUN:
                skipped_queue += 1
                reached_limit = True
                continue

            try:
                reply_text = writer.write_reply(comment_text, username, post_text)
            except Exception as e:
                print(f"[reply_bot] writer 실패 ({cid}): {e}")
                continue

            try:
                rid = threads_client.publish_reply(cid, reply_text)
                db.record_reply(cid, post_id, rid)
                replied += 1
                print(f"[reply_bot] ✅ @{username}: {comment_text[:50]} → {reply_text[:50]}")

                # 다음 답글 전 랜덤 딜레이 (마지막엔 생략)
                if replied < MAX_REPLIES_PER_RUN:
                    delay = random.uniform(REPLY_DELAY_MIN, REPLY_DELAY_MAX)
                    print(f"[reply_bot] ⏱  {delay:.1f}초 대기 (사람처럼)")
                    time.sleep(delay)
            except threads_client.ThreadsError as e:
                print(f"[reply_bot] publish_reply 실패 ({cid}): {e}")

    if skipped_self:
        print(f"[reply_bot] 🛡  본인 답글 {skipped_self}개 보호 (self-check)")
    if skipped_queue:
        print(f"[reply_bot] ⏳ 한도 초과로 {skipped_queue}개 미답글 대기 → 다음 사이클(15분 후) 처리")
    print(f"[reply_bot] 총 {replied}/{MAX_REPLIES_PER_RUN}개 답글 게시")
    return replied
