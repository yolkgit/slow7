"""슬로우7 워드프레스 자동 발행 스크립트.

사용법:
    python -m scripts.publish_blog            # 토픽 자동 선택 후 발행
    python -m scripts.publish_blog m_fat_burn # 특정 토픽 키 지정

흐름:
    1) 최근 안 쓴 토픽 선택 (성과 가중)
    2) Claude로 SEO 블로그 글 생성 (제목/본문HTML/메타/태그)
    3) 카드 썸네일 생성 → 워드프레스에 대표이미지 업로드
    4) 워드프레스에 글 발행
    5) DB에 이력 기록 (중복 방지 + 성과 추적)
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import blog_writer, card_generator, config, db, image_search, topics, wordpress_client


def _insert_before_disclaimer(content_html: str, html_block: str) -> str:
    """면책 문구(<hr>로 시작) 앞에 블록 삽입. 없으면 맨 끝에."""
    idx = content_html.rfind("<hr>")
    if idx >= 0:
        return content_html[:idx] + html_block + "\n" + content_html[idx:]
    return content_html.rstrip() + "\n" + html_block


def _insert_after_first_h2(content_html: str, html_block: str) -> str:
    """첫 번째 </h2> 다음에 블록 삽입 (본문 중간 이미지용)."""
    import re
    m = re.search(r"</h2>", content_html)
    if m:
        pos = m.end()
        return content_html[:pos] + "\n" + html_block + "\n" + content_html[pos:]
    # h2 없으면 첫 문단 뒤
    m = re.search(r"</p>", content_html)
    if m:
        pos = m.end()
        return content_html[:pos] + "\n" + html_block + "\n" + content_html[pos:]
    return html_block + "\n" + content_html


def _build_related_links_html(exclude_wp_id: str | None) -> str:
    """발행된 글 중 최대 4개를 '함께 읽으면 좋은 글'로."""
    links = db.published_blog_links(limit=4, exclude_wp_id=exclude_wp_id)
    if not links:
        return ""
    items = "".join(f'<li><a href="{l["link"]}">{l["title"]}</a></li>' for l in links)
    return f"<h2>함께 읽으면 좋은 글</h2>\n<ul>{items}</ul>"


def main(topic_key: str | None = None) -> int:
    missing = config.validate_wp(require_claude=True)
    if missing:
        print(f"환경변수 누락: {missing}")
        return 2

    db.init()
    exclude = set(db.recent_topic_keys(limit=30))

    # 토픽 선택
    if topic_key:
        topic = next((t for t in topics.all_topics() if t.key == topic_key), None)
        if not topic:
            print(f"토픽 키 못 찾음: {topic_key}")
            return 2
        if topic_key in exclude:
            print(f"⚠️  '{topic_key}'는 최근 발행한 토픽이야. 비슷한 글 중복 위험! "
                  f"(그래도 진행 — 내용은 최근 제목과 차별화됨)")
    else:
        # 블로그는 slot 구분 없이 전체 풀에서 성과 가중 선택
        import random
        scores = db.topic_scores()
        all_pool = topics.all_topics()
        candidates = [t for t in all_pool if t.key not in exclude] or all_pool

        # 최근 3개 글의 주제군을 피해서 같은 군 연달아 방지
        recent_keys = db.recent_topic_keys(limit=3)
        recent_clusters = {topics.topic_cluster(k) for k in recent_keys}
        fresh = [t for t in candidates if topics.topic_cluster(t.key) not in recent_clusters]
        pool = fresh if fresh else candidates  # 다 걸리면 원래 후보로

        if scores:
            weights = [scores.get(t.key, 0) + 1.0 for t in pool]
            topic = random.choices(pool, weights=weights, k=1)[0]
        else:
            topic = random.choice(pool)

    level = topics.topic_level(topic)
    print(f"[blog] 토픽: {topic.key} ({topic.title}) [난이도: {level}]")

    # 글 생성 (최근 발행 제목을 줘서 내용 중복 방지)
    recent_titles = db.recent_post_titles(limit=12)
    post = blog_writer.write_blog_post(topic, recent_titles)
    print(f"[blog] 제목: {post['title']}")
    print(f"[blog] 슬러그: {post['slug']}")
    print(f"[blog] 메타: {post['meta_description']}")
    print(f"[blog] 태그: {post['tags']}")

    # 본문 이미지 (Pexels) — 첫 H2 뒤에 삽입
    try:
        photo = image_search.search_and_download(topic.title, post.get("tags", []))
        if photo:
            img_id = wordpress_client.upload_media(photo["path"], alt_text=photo["alt"])
            src = wordpress_client.media_url(img_id) if img_id else ""
            if src:
                caption = (
                    f'<figure><img src="{src}" alt="{photo["alt"]}" '
                    f'style="max-width:100%;height:auto;border-radius:8px;">'
                    f'<figcaption style="font-size:0.75em;color:#aaa;text-align:center;">'
                    f'Photo by <a href="{photo["photographer_url"]}" rel="nofollow" target="_blank">'
                    f'{photo["photographer"]}</a> on Pexels</figcaption></figure>'
                )
                post["content_html"] = _insert_after_first_h2(post["content_html"], caption)
                print(f"[blog] 본문 이미지 삽입 (Pexels: {photo['query']})")
            try:
                photo["path"].unlink(missing_ok=True)
            except Exception:
                pass
        else:
            print("[blog] Pexels 미설정/결과없음 → 본문 이미지 생략")
    except Exception as e:
        print(f"[blog] 본문 이미지 실패(무시): {e}")

    # 내부 링크 (발행된 글 → '함께 읽으면 좋은 글')
    related = _build_related_links_html(exclude_wp_id=None)
    if related:
        post["content_html"] = _insert_before_disclaimer(post["content_html"], related)
        print("[blog] 내부 링크 삽입")

    print(f"[blog] 본문 길이: {len(post['content_html'])}자")

    # 대표 이미지 (카드 썸네일)
    featured_id = None
    if config.ATTACH_CARD_IMAGE:
        try:
            filename = f"{int(time.time())}_{topic.key}.png"
            out_path = config.MEDIA_DIR / filename
            card_generator.generate(
                post.get("card_title") or topic.title,
                post.get("card_subtitle") or topic.angle,
                "evening",  # 블로그는 저녁 톤(과학/정보) 색감 사용
                out_path,
            )
            print(f"[blog] 썸네일 생성: {out_path}")
            mid = wordpress_client.upload_media(out_path, alt_text=post["title"])
            featured_id = mid or None
            print(f"[blog] 대표이미지 media_id={featured_id}")
        except Exception as e:
            print(f"[blog] 썸네일 처리 실패(무시하고 진행): {e}")

    # 검수 모드면 무조건 draft로 생성 (사용자 '발행' 응답 후 공개)
    status = "draft" if config.REVIEW_MODE else config.WP_POST_STATUS

    try:
        result = wordpress_client.create_post(
            title=post["title"],
            content_html=post["content_html"],
            excerpt=post["meta_description"],
            category=level,  # 난이도 카테고리 (초급/중급/고급)
            tags=post["tags"],
            featured_media_id=featured_id,
            slug=post["slug"],
            status=status,
            yoast_metadesc=post["meta_description"],
            yoast_focuskw=(post["tags"][0] if post.get("tags") else None),
        )
    except wordpress_client.WordPressError as e:
        print(f"[blog] ❌ 생성 실패: {e}")
        return 1

    link = result.get("link", "(unknown)")
    wp_id = result.get("id", 0)
    print(f"[blog] ✅ 초안 생성 완료 (status={status}): {link}")

    # DB 기록
    db.record_post(str(wp_id) if wp_id else None, "blog", topic.key, post["title"], link)

    # 검수 모드 — 검수 큐 등록 + 텔레그램 알림
    if config.REVIEW_MODE and wp_id:
        db.add_review(str(wp_id), topic.key, post["title"], link, post["content_html"])
        _notify_telegram(post, link, wp_id)

    return 0


def _strip_html(html: str, limit: int = 400) -> str:
    """HTML 태그 제거하고 미리보기 텍스트 추출."""
    import re
    text = re.sub(r"<[^>]+>", "", html)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit] + ("…" if len(text) > limit else "")


def _notify_telegram(post: dict, link: str, wp_id) -> None:
    """검수 알림 발송."""
    if not config.TELEGRAM_BOT_TOKEN or not config.TELEGRAM_CHAT_ID:
        print("[blog] 텔레그램 미설정 → 알림 생략 (draft로만 저장됨)")
        return
    try:
        from src import telegram_client
        preview = _strip_html(post["content_html"], 350)
        pending = db.pending_review_count()
        msg = (
            f"📝 <b>새 블로그 초안</b> (대기 {pending}개)\n\n"
            f"<b>{post['title']}</b>\n\n"
            f"{preview}\n\n"
            f"🏷 {' '.join('#'+t for t in post.get('tags', [])[:5])}\n"
            f"🔗 <a href=\"{link}\">미리보기</a>\n\n"
            f"━━━━━━━━━━\n"
            f"✅ 좋으면 <b>발행</b> 이라고 답장\n"
            f"✏️ 고칠 게 있으면 수정 내용을 그대로 답장\n"
            f"   (예: \"마지막 문단 더 짧게\", \"제목 더 자극적으로\")"
        )
        telegram_client.send_message(msg)
        print("[blog] 📱 텔레그램 검수 알림 전송 완료")
    except Exception as e:
        print(f"[blog] 텔레그램 알림 실패(무시): {e}")


if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else None
    raise SystemExit(main(arg))
