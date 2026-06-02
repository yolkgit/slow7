"""카드 이미지 미리보기 — 셋업 전에 디자인 확인용.

    python -m scripts.preview_card
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import card_generator, config


def main() -> int:
    out = config.MEDIA_DIR / "preview_morning.png"
    card_generator.generate("7분 페이스로", "오늘도 한 걸음, 가자!", "morning", out)
    print(f"saved: {out}")
    out = config.MEDIA_DIR / "preview_noon.png"
    card_generator.generate("앞꿈치 착지", "무릎이 안 아픈 비밀, 이거다!", "noon", out)
    print(f"saved: {out}")
    out = config.MEDIA_DIR / "preview_evening.png"
    card_generator.generate("Zone 2의 과학", "느려야 미토콘드리아가 늘어난다", "evening", out)
    print(f"saved: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
