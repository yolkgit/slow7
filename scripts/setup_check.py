"""환경 점검 — API 키와 토큰이 잘 들어있는지 확인 후 me() 호출."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import config, threads_client


def main() -> int:
    print("=== Slow7 환경 점검 ===")
    print(f"ANTHROPIC_MODEL : {config.ANTHROPIC_MODEL}")
    print(f"DRY_RUN         : {config.DRY_RUN}")
    print(f"ATTACH_CARD     : {config.ATTACH_CARD_IMAGE}")
    print(f"AUTO_REPLY      : {config.AUTO_REPLY_ENABLED}")

    missing = config.validate()
    if missing:
        print(f"\n❌ 누락된 환경 변수: {missing}")
        return 1

    print("\n→ Threads /me 호출 중...")
    try:
        me = threads_client.me()
        print(f"✅ 연결 성공: id={me.get('id')} username=@{me.get('username')}")
    except threads_client.ThreadsError as e:
        print(f"❌ Threads API 실패: {e}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
