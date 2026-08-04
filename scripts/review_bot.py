"""텔레그램 검수 봇 — 사용자 응답을 읽어 발행/수정 처리.

cron으로 주기적 실행 (예: 15분마다).

흐름:
    1) getUpdates로 새 메시지 수신 (마지막 update_id 이후)
    2) 가장 오래된 '검수 대기(pending)' 글에 명령 적용
       - "발행"/"ok"/"공개"  → 워드프레스 status=publish 로 전환
       - "건너뛰기"/"skip"   → 검수 큐에서 제외 (draft 유지)
       - 그 외 텍스트        → 수정 지시로 해석 → Claude 수정 → draft 갱신 → 재알림
    3) 처리한 update_id 저장 (중복 방지)
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import blog_writer, config, db, telegram_client, wordpress_client

PUBLISH_WORDS = {"발행", "공개", "ok", "ok!", "오케이", "좋아", "굿", "publish", "go"}
SKIP_WORDS = {"건너뛰기", "스킵", "skip", "패스", "보류"}

LAST_UPDATE_KEY = "tg_last_update_id"


def _publish(review: dict) -> None:
    wp_id = review["wp_post_id"]
    try:
        result = wordpress_client.update_post(wp_id, status="publish")
        link = result.get("link", review.get("wp_link", ""))
        db.mark_review_status(wp_id, "published")
        telegram_client.send_message(f"✅ <b>발행 완료!</b>\n🔗 <a href=\"{link}\">{review['title']}</a>")
        print(f"[review] 발행: {wp_id}")
        _send_push(review, link)
        _send_naver_summary(review, link)
    except wordpress_client.WordPressError as e:
        telegram_client.send_message(f"❌ 발행 실패: {e}")
        print(f"[review] 발행 실패 {wp_id}: {e}")


def _send_push(review: dict, link: str) -> None:
    """새 글 웹 푸시 발송. 실패해도 발행 흐름을 막지 않는다."""
    try:
        from src import webpush

        result = webpush.send_new_post(title=review["title"], url=link)
        if result["sent"]:
            telegram_client.send_message(
                f"🔔 푸시 발송 {result['sent']}명"
                + (f" (실패 {result['failed']})" if result["failed"] else "")
            )
    except Exception as e:
        print(f"[review] 푸시 발송 실패(무시): {e}")


def _send_naver_summary(review: dict, link: str) -> None:
    """발행 후 네이버 블로그용 요약본을 텔레그램으로 전송 (수동 복붙용)."""
    import html as _html
    try:
        from src import social_writer
        summary = social_writer.write_naver_summary(
            review["title"], review.get("content_html", ""), link
        )
        msg = (
            "📋 <b>네이버 블로그용 요약본</b>\n"
            "(아래를 복사해서 네이버 블로그 앱에 붙여넣어)\n"
            "━━━━━━━━━━\n\n"
            f"{_html.escape(summary)}"
        )
        telegram_client.send_message(msg)
        print("[review] 네이버 요약본 전송 완료")
    except Exception as e:
        print(f"[review] 네이버 요약본 실패(무시): {e}")


def _skip(review: dict) -> None:
    db.mark_review_status(review["wp_post_id"], "skipped")
    telegram_client.send_message(
        f"⏭ <b>{review['title']}</b> 검수 큐에서 제외했어 (draft로 남아있음).\n"
        f"다음 대기 글로 넘어갈게."
    )
    _announce_next()


def _revise(review: dict, instruction: str) -> None:
    wp_id = review["wp_post_id"]
    telegram_client.send_message("✏️ 수정 중... 잠깐만!")
    try:
        revised = blog_writer.revise_blog_post(
            review["title"], review["content_html"], instruction
        )
        wordpress_client.update_post(
            wp_id, title=revised["title"], content_html=revised["content_html"]
        )
        db.update_review_content(wp_id, revised["content_html"], revised["title"])
        preview = _strip_html(revised["content_html"], 350)
        msg = (
            f"✏️ <b>수정했어!</b>\n\n"
            f"<b>{revised['title']}</b>\n\n"
            f"{preview}\n\n"
            f"🔗 <a href=\"{review['wp_link']}\">미리보기</a>\n\n"
            f"━━━━━━━━━━\n"
            f"✅ 이제 좋으면 <b>발행</b>\n"
            f"✏️ 더 고칠 거 있으면 또 답장"
        )
        telegram_client.send_message(msg)
        print(f"[review] 수정 완료: {wp_id}")
    except Exception as e:
        telegram_client.send_message(f"❌ 수정 실패: {e}\n다시 시도해줘.")
        print(f"[review] 수정 실패 {wp_id}: {e}")


def _announce_next() -> None:
    """다음 대기 글이 있으면 안내."""
    nxt = db.oldest_pending_review()
    if not nxt:
        telegram_client.send_message("📭 검수 대기 글이 더 없어. 다음 자동 생성 때 또 알려줄게!")
        return
    preview = _strip_html(nxt["content_html"], 350)
    msg = (
        f"📝 <b>다음 검수 글</b>\n\n"
        f"<b>{nxt['title']}</b>\n\n"
        f"{preview}\n\n"
        f"🔗 <a href=\"{nxt['wp_link']}\">미리보기</a>\n\n"
        f"✅ <b>발행</b> / ✏️ 수정 내용 답장 / ⏭ <b>건너뛰기</b>"
    )
    telegram_client.send_message(msg)


def _strip_html(html: str, limit: int = 350) -> str:
    import re
    text = re.sub(r"<[^>]+>", "", html)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit] + ("…" if len(text) > limit else "")


def _handle_text(text: str) -> None:
    text = text.strip()
    low = text.lower()
    review = db.oldest_pending_review()
    if not review:
        telegram_client.send_message("📭 지금 검수 대기 중인 글이 없어. 새 글 생성되면 알려줄게!")
        return

    if low in PUBLISH_WORDS:
        _publish(review)
        _announce_next()
    elif low in SKIP_WORDS:
        _skip(review)
    else:
        # 그 외 텍스트는 수정 지시
        _revise(review, text)


def run() -> int:
    missing = config.validate_wp(require_claude=True)
    if missing:
        print(f"환경변수 누락: {missing}")
        return 2
    if not config.TELEGRAM_BOT_TOKEN or not config.TELEGRAM_CHAT_ID:
        print("텔레그램 미설정 (TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID)")
        return 2

    db.init()
    last_id_str = db.kv_get(LAST_UPDATE_KEY)
    offset = (int(last_id_str) + 1) if last_id_str else None

    updates = telegram_client.get_updates(offset=offset)
    if not updates:
        print("[review] 새 메시지 없음")
        return 0

    max_update_id = None
    for u in updates:
        max_update_id = u["update_id"]
        msg = u.get("message") or u.get("edited_message")
        if not msg:
            continue
        # 본인 chat만 처리
        chat_id = str((msg.get("chat") or {}).get("id", ""))
        if config.TELEGRAM_CHAT_ID and chat_id != str(config.TELEGRAM_CHAT_ID):
            continue
        text = msg.get("text", "")
        if not text:
            continue
        print(f"[review] 수신: {text[:60]}")
        try:
            _handle_text(text)
        except Exception as e:
            print(f"[review] 처리 오류: {e}")

    if max_update_id is not None:
        db.kv_set(LAST_UPDATE_KEY, str(max_update_id))
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
