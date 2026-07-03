"""SNS 크로스포스팅 클라이언트 패키지.

각 플랫폼 모듈은 post(text: str) -> str|None 함수를 제공.
enabled() 로 설정 여부 판단.
"""
from __future__ import annotations

from .. import config


def enabled_platforms() -> list[str]:
    """설정된 플랫폼 목록. SNS_PLATFORMS 우선, 없으면 토큰 있는 것 자동 감지."""
    if config.SNS_PLATFORMS.strip():
        return [p.strip() for p in config.SNS_PLATFORMS.split(",") if p.strip()]
    detected = []
    if config.X_API_KEY and config.X_ACCESS_TOKEN:
        detected.append("x")
    if config.FB_PAGE_ID and config.FB_PAGE_TOKEN:
        detected.append("facebook")
    if config.THREADS_PROMO_TOKEN and config.THREADS_PROMO_USER_ID:
        detected.append("threads")
    if config.IG_USER_ID and config.IG_ACCESS_TOKEN:
        detected.append("instagram")
    return detected


def post_to(platform: str, text: str, image_url: str | None = None) -> str | None:
    """플랫폼별 게시. 성공 시 sns_post_id, 실패 시 예외."""
    if config.DRY_RUN:
        print(f"[DRY_RUN] {platform} 게시: {text[:80]}")
        return "dry-run"
    if platform == "x":
        from . import x_client
        return x_client.post(text)
    if platform == "facebook":
        from . import facebook_client
        return facebook_client.post(text)
    if platform == "threads":
        from . import threads_promo
        return threads_promo.post(text)
    if platform == "instagram":
        from . import instagram_client
        return instagram_client.post(text, image_url)
    raise ValueError(f"unknown platform: {platform}")
