"""SNS 연결 점검 — 설정된 플랫폼 인증 확인."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import config, social


def main() -> int:
    platforms = social.enabled_platforms()
    print("=== Slow7 SNS 연결 점검 ===")
    print(f"활성 플랫폼: {platforms or '(없음)'}\n")
    if not platforms:
        print("설정된 플랫폼이 없어. .env에 토큰을 넣거나 SNS_PLATFORMS를 설정해줘.")
        return 1

    for p in platforms:
        print(f"→ {p} 확인 중...")
        try:
            if p == "x":
                from src.social import x_client
                me = x_client.verify()
                print(f"  ✅ X: @{me.get('data', {}).get('username')}")
            elif p == "facebook":
                from src.social import facebook_client
                pg = facebook_client.verify()
                print(f"  ✅ FB 페이지: {pg.get('name')} (팬 {pg.get('fan_count', 0)})")
            elif p == "threads":
                print("  ℹ️  스레드는 게시 테스트로만 확인 가능 (verify 없음)")
            elif p == "instagram":
                print("  ℹ️  인스타는 이미지 게시 테스트로만 확인 가능")
        except Exception as e:
            print(f"  ❌ {p} 실패: {e}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
