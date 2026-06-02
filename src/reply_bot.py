"""최근 내 게시물의 댓글을 폴링해 미답글에 자동 응답."""
from __future__ import annotations

from . import config, db, threads_client, writer


def run(max_posts: int = 10, dry_run: bool | None = None) -> int:
    """답글을 단 개수를 반환."""
    if dry_run is None:
        dry_run = config.DRY_RUN
    if not config.AUTO_REPLY_ENABLED:
        print("[reply_bot] AUTO_REPLY_ENABLED=false → skip")
        return 0

    db.init()
    my_id = config.THREADS_USER_ID
    posts = threads_client.fetch_user_posts(limit=max_posts)
    replied = 0

    for post in posts:
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
            # 내 답글은 건너뜀
            from_user = (c.get("from") or {}).get("id") or ""
            if str(from_user) == str(my_id):
                continue
            if db.has_replied(cid):
                continue
            comment_text = (c.get("text") or "").strip()
            username = c.get("username") or (c.get("from") or {}).get("username")
            if not comment_text:
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
            except threads_client.ThreadsError as e:
                print(f"[reply_bot] publish_reply 실패 ({cid}): {e}")

    print(f"[reply_bot] 총 {replied}개 답글 게시")
    return replied
