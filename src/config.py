"""환경 변수 로딩 + 공통 상수."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")


def _bool(name: str, default: bool = False) -> bool:
    v = os.getenv(name, "").strip().lower()
    if not v:
        return default
    return v in ("1", "true", "yes", "y", "on")


THREADS_ACCESS_TOKEN = os.getenv("THREADS_ACCESS_TOKEN", "")
THREADS_USER_ID = os.getenv("THREADS_USER_ID", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001")

GITHUB_REPO = os.getenv("GITHUB_REPO", "")
GITHUB_BRANCH = os.getenv("GITHUB_BRANCH", "main")

# ===== WordPress =====
WP_SITE_URL = os.getenv("WP_SITE_URL", "").rstrip("/")   # 예: https://slow7.co.kr
WP_USERNAME = os.getenv("WP_USERNAME", "")               # 워드프레스 로그인 아이디
WP_APP_PASSWORD = os.getenv("WP_APP_PASSWORD", "")       # Application Password (공백 포함 가능)
WP_DEFAULT_CATEGORY = os.getenv("WP_DEFAULT_CATEGORY", "슬로우조깅")
WP_POST_STATUS = os.getenv("WP_POST_STATUS", "publish")  # publish | draft

# ===== Telegram (검수 봇) =====
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

ATTACH_CARD_IMAGE = _bool("ATTACH_CARD_IMAGE", True)
AUTO_REPLY_ENABLED = _bool("AUTO_REPLY_ENABLED", True)
# 검수 모드: true면 생성 후 draft+텔레그램 알림, 사용자 '발행' 응답 시 공개
REVIEW_MODE = _bool("REVIEW_MODE", True)
DRY_RUN = _bool("DRY_RUN", False)

BRAND_NAME = "슬로우7"
BRAND_SLOGAN = "7분 페이스로 극강의 효율"
LOGO_PATH = ROOT / "assets" / "logo.png"
DB_PATH = ROOT / "slow7.db"
MEDIA_DIR = ROOT / "posted_media"


def validate(require_threads: bool = True, require_claude: bool = True) -> list[str]:
    """누락된 환경 변수를 리스트로 반환. 빈 리스트면 OK."""
    missing: list[str] = []
    if require_claude and not ANTHROPIC_API_KEY:
        missing.append("ANTHROPIC_API_KEY")
    if require_threads:
        if not THREADS_ACCESS_TOKEN:
            missing.append("THREADS_ACCESS_TOKEN")
        if not THREADS_USER_ID:
            missing.append("THREADS_USER_ID")
    return missing


def validate_wp(require_claude: bool = True) -> list[str]:
    """워드프레스 발행에 필요한 환경 변수 점검."""
    missing: list[str] = []
    if require_claude and not ANTHROPIC_API_KEY:
        missing.append("ANTHROPIC_API_KEY")
    if not WP_SITE_URL:
        missing.append("WP_SITE_URL")
    if not WP_USERNAME:
        missing.append("WP_USERNAME")
    if not WP_APP_PASSWORD:
        missing.append("WP_APP_PASSWORD")
    return missing
