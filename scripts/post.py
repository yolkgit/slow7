"""슬로우7 자동 게시 스크립트.

GitHub Actions에서 이미지 raw URL을 사용하기 위해 2단계로 동작:

    python -m scripts.post prepare <slot>   # 글+이미지 생성 → .pending.json 저장
    (워크플로우가 git push로 이미지 공개)
    python -m scripts.post publish          # .pending.json 읽고 Threads에 게시

로컬에서 한방에 돌리려면 (DRY_RUN 추천):
    python -m scripts.post oneshot <slot>
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import card_generator, config, db, threads_client, topics, writer

PENDING_PATH = Path(__file__).resolve().parent.parent / ".pending.json"


def prepare(slot: str) -> int:
    if slot not in {"morning", "noon", "evening"}:
        print(f"unknown slot: {slot}")
        return 2

    missing = config.validate(require_threads=False, require_claude=True)
    if missing:
        print(f"환경변수 누락: {missing}")
        return 2

    db.init()
    exclude = set(db.recent_topic_keys(limit=30))
    scores = db.topic_scores()  # 성과 데이터 있으면 잘된 토픽 가중
    topic = topics.pick(slot, exclude_keys=exclude, scores=scores)
    score_note = f" (성과가중 {len(scores)}개 토픽 반영)" if scores else ""
    print(f"[prepare] slot={slot} topic={topic.key} ({topic.title}){score_note}")

    content = writer.write_post(topic, list(exclude)[:10])
    text = content["text"]
    print("[prepare] ----- text -----")
    print(text)
    print("[prepare] ----------------")

    image_filename = None
    image_url = None
    if config.ATTACH_CARD_IMAGE:
        filename = f"{int(time.time())}_{topic.key}.png"
        out_path = config.MEDIA_DIR / filename
        card_generator.generate(
            content.get("card_title") or topic.title,
            content.get("card_subtitle") or topic.angle,
            slot,
            out_path,
        )
        image_filename = filename
        image_url = card_generator.public_url_for(filename)
        print(f"[prepare] 카드 저장: {out_path}")
        print(f"[prepare] 예정 URL: {image_url}")

    pending = {
        "slot": slot,
        "topic_key": topic.key,
        "text": text,
        "image_filename": image_filename,
        "image_url": image_url,
    }
    PENDING_PATH.write_text(json.dumps(pending, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[prepare] saved: {PENDING_PATH}")
    return 0


def publish() -> int:
    missing = config.validate(require_threads=not config.DRY_RUN, require_claude=False)
    if missing:
        print(f"환경변수 누락: {missing}")
        return 2
    if not PENDING_PATH.exists():
        print(f"❌ {PENDING_PATH} 없음 — prepare 먼저 실행")
        return 2

    p = json.loads(PENDING_PATH.read_text(encoding="utf-8"))
    text, image_url = p["text"], p.get("image_url")
    db.init()

    try:
        media_id = threads_client.publish_post(text, image_url=image_url)
    except threads_client.ThreadsError as e:
        if image_url:
            print(f"[publish] 이미지 실패 → 텍스트 폴백: {e}")
            media_id = threads_client.publish_post(text, image_url=None)
            image_url = None
        else:
            raise

    db.record_post(media_id, p["slot"], p["topic_key"], text, image_url)
    print(f"[publish] ✅ media_id={media_id}")

    # pending 정리
    PENDING_PATH.unlink(missing_ok=True)
    return 0


def oneshot(slot: str) -> int:
    rc = prepare(slot)
    if rc != 0:
        return rc
    return publish()


def main(argv: list[str]) -> int:
    if not argv:
        print("usage: post.py {prepare|publish|oneshot} [slot]")
        return 2
    cmd = argv[0]
    if cmd == "prepare":
        return prepare(argv[1] if len(argv) > 1 else "morning")
    if cmd == "publish":
        return publish()
    if cmd == "oneshot":
        return oneshot(argv[1] if len(argv) > 1 else "morning")
    # 하위호환: post.py morning → oneshot morning
    if cmd in {"morning", "noon", "evening"}:
        return oneshot(cmd)
    print(f"unknown command: {cmd}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
