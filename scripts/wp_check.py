"""워드프레스 연결 점검 — 발행 전에 인증이 되는지 확인."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import config, wordpress_client


def main() -> int:
    print("=== Slow7 WordPress 연결 점검 ===")
    print(f"WP_SITE_URL : {config.WP_SITE_URL}")
    print(f"WP_USERNAME : {config.WP_USERNAME}")
    print(f"APP_PASSWORD: {'*' * len(config.WP_APP_PASSWORD)} ({len(config.WP_APP_PASSWORD)}자)")
    print(f"카테고리    : {config.WP_DEFAULT_CATEGORY}")
    print(f"발행 상태   : {config.WP_POST_STATUS}")

    missing = config.validate_wp(require_claude=False)
    if missing:
        print(f"\n❌ 누락된 환경 변수: {missing}")
        return 1

    print("\n→ WordPress /users/me 호출 중...")
    try:
        me = wordpress_client.whoami()
        print(f"✅ 연결 성공: id={me.get('id')} name={me.get('name')} ")
        roles = me.get("roles", [])
        print(f"   권한: {roles}")
        if "administrator" not in roles and "author" not in roles and "editor" not in roles:
            print("   ⚠️  글 발행 권한이 없을 수 있음 (author 이상 필요)")
    except wordpress_client.WordPressError as e:
        print(f"❌ 연결 실패: {e}")
        print("\n점검 사항:")
        print("  - WP_SITE_URL이 정확한지 (https:// 포함, 끝 슬래시 없이)")
        print("  - Application Password가 맞는지 (공백 포함 그대로)")
        print("  - 워드프레스가 REST API를 허용하는지 (보안 플러그인 확인)")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
