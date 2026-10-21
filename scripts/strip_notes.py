"""공개된 글에 남은 작업 메모("[작성 근거 노트 — 발행 전 확인용]" 등)를 지운다.

    python -m scripts.strip_notes            # 어느 글에 있는지만 출력
    python -m scripts.strip_notes --apply    # 실제로 지움 (API 비용 없음)
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import quality, wordpress_client as wp  # noqa: E402


def main() -> int:
    apply = "--apply" in sys.argv
    found = 0
    for p in wp.list_posts_raw("publish"):
        before = p["content"]["raw"]
        after, n = quality.strip_internal_notes(before)
        if not n:
            continue
        found += 1
        print(f"{p['id']} {p['title']['raw']}  메모 {n}개  {p['link']}")
        if apply:
            wp.update_post(p["id"], content_html=after)
            print("   ✅ 제거")
    print(f"\n메모가 있던 글 {found}편" + ("" if apply else " — 지우려면 --apply"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
