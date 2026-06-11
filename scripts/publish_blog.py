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

from src import blog_writer, card_generator, config, db, topics, wordpress_client


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
    else:
        # 블로그는 slot 구분 없이 전체 풀에서 성과 가중 선택
        scores = db.topic_scores()
        all_pool = topics.all_topics()
        candidates = [t for t in all_pool if t.key not in exclude] or all_pool
        # 성과 가중 (topics.pick은 slot용이라 직접 구현)
        import random
        if scores:
            weights = [scores.get(t.key, 0) + 1.0 for t in candidates]
            topic = random.choices(candidates, weights=weights, k=1)[0]
        else:
            topic = random.choice(candidates)

    print(f"[blog] 토픽: {topic.key} ({topic.title})")

    # 글 생성
    post = blog_writer.write_blog_post(topic, list(exclude)[:10])
    print(f"[blog] 제목: {post['title']}")
    print(f"[blog] 슬러그: {post['slug']}")
    print(f"[blog] 메타: {post['meta_description']}")
    print(f"[blog] 태그: {post['tags']}")
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

    # 발행
    try:
        result = wordpress_client.create_post(
            title=post["title"],
            content_html=post["content_html"],
            excerpt=post["meta_description"],
            category=config.WP_DEFAULT_CATEGORY,
            tags=post["tags"],
            featured_media_id=featured_id,
            slug=post["slug"],
        )
    except wordpress_client.WordPressError as e:
        print(f"[blog] ❌ 발행 실패: {e}")
        return 1

    link = result.get("link", "(unknown)")
    wp_id = result.get("id", 0)
    print(f"[blog] ✅ 발행 완료: {link}")

    # DB 기록 (threads_id 칸을 wp post id로 재활용)
    db.record_post(str(wp_id) if wp_id else None, "blog", topic.key, post["title"], link)
    return 0


if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else None
    raise SystemExit(main(arg))
