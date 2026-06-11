"""텔레그램 봇 점검 + chat_id 확인.

사용법:
    1) BotFather에서 봇 만들고 토큰을 .env의 TELEGRAM_BOT_TOKEN 에 넣기
    2) 텔레그램에서 그 봇과 대화 시작 → 아무 메시지나 보내기 (예: "안녕")
    3) python -m scripts.tg_check  → 너의 chat_id가 출력됨
    4) 그 chat_id를 .env의 TELEGRAM_CHAT_ID 에 넣기
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import config, telegram_client


def main() -> int:
    if not config.TELEGRAM_BOT_TOKEN:
        print("❌ TELEGRAM_BOT_TOKEN 미설정. BotFather에서 봇 만들고 .env에 넣어줘.")
        return 1

    print("→ 봇 정보 확인...")
    try:
        me = telegram_client.get_me()
        print(f"✅ 봇 연결 성공: @{me.get('username')} ({me.get('first_name')})")
    except Exception as e:
        print(f"❌ 봇 토큰 오류: {e}")
        return 1

    print("\n→ 최근 메시지에서 chat_id 찾는 중...")
    print("  (봇과 대화를 시작하고 아무 메시지나 먼저 보냈어야 함)")
    updates = telegram_client.get_updates()
    if not updates:
        print("\n⚠️  메시지가 없어. 텔레그램에서 봇에게 '안녕' 같은 메시지를 먼저 보내고 다시 실행해줘.")
        return 1

    chat_ids = set()
    for u in updates:
        msg = u.get("message") or u.get("edited_message") or {}
        chat = msg.get("chat") or {}
        if chat.get("id"):
            name = chat.get("first_name") or chat.get("title") or ""
            chat_ids.add((str(chat["id"]), name))

    if not chat_ids:
        print("⚠️  chat_id를 못 찾음. 봇에게 메시지 보내고 다시.")
        return 1

    print("\n발견된 chat_id:")
    for cid, name in chat_ids:
        print(f"  📌 {cid}  ({name})")
    print("\n→ 위 chat_id를 .env 의 TELEGRAM_CHAT_ID 에 넣어줘.")

    if config.TELEGRAM_CHAT_ID:
        print(f"\n현재 설정된 TELEGRAM_CHAT_ID: {config.TELEGRAM_CHAT_ID}")
        print("→ 테스트 메시지 전송...")
        try:
            telegram_client.send_message("🔔 슬로우7 검수봇 연결 성공! 이제 새 글 초안을 여기로 보내줄게 🔥")
            print("✅ 전송 완료! 텔레그램 확인해봐.")
        except Exception as e:
            print(f"❌ 전송 실패: {e}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
