"""공개된 글에 남은 작업 메모("[작성 근거 노트 — 발행 전 확인용]" 등)·찌꺼기 문단을 지우고,
빠진 의료 면책 문구를 끝에 붙인다.

    python -m scripts.strip_notes            # 어느 글에 있는지만 출력
    python -m scripts.strip_notes --apply    # 실제로 지움 (API 비용 없음)
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import quality, wordpress_client as wp  # noqa: E402
from src.blog_writer import DISCLAIMER_HTML  # noqa: E402

DISCLAIMER_MARK = "※ 이 글은"



def main() -> int:
    apply = "--apply" in sys.argv
    found = 0
    for p in wp.list_posts_raw("publish"):
        before = p["content"]["raw"]
        after, n = quality.strip_internal_notes(before)
        # 건강 글은 모두 의료 면책 문구로 끝나야 한다 (초기 글·메모 제거로 빠진 글 보충)
        restore = DISCLAIMER_MARK not in after
        if restore:
            after = after.rstrip() + "\n\n" + DISCLAIMER_HTML
        if not n and not restore:
            continue
        found += 1
        print(f"{p['id']} {p['title']['raw']}  메모 {n}개{'  면책 문구 추가' if restore else ''}  {p['link']}")
        if apply:
            wp.update_post(p["id"], content_html=after)
            print("   ✅ 반영")
    print(f"\n고칠 글 {found}편" + ("" if apply else " — 반영하려면 --apply"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
