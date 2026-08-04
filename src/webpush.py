"""웹 푸시 발송.

구독 정보는 워드프레스가 보관하고(mu-plugins/slow7-push.php), 발송만 여기서 한다.
VAPID 개인키를 봇의 .env 한 곳에만 두기 위한 구조다.

새 글 발행 시 scripts/review_bot.py 의 _publish() 에서 호출된다.

필요 환경변수:
    VAPID_PUBLIC_KEY   브라우저 구독에 쓰는 공개키 (워드프레스 옵션과 동일해야 함)
    VAPID_PRIVATE_KEY  발송 서명용 개인키 (절대 노출 금지)
    VAPID_SUBJECT      mailto:... 형식 연락처 (푸시 서비스 요구사항)
"""
from __future__ import annotations

import json
import os

import requests

from src import config

# 만료·해지된 구독에 대한 푸시 서비스 응답. 이 코드가 오면 구독을 지운다.
_GONE = (404, 410)

TIMEOUT = 20


def _wp_auth() -> tuple[str, str]:
    return (config.WP_USERNAME, config.WP_APP_PASSWORD)


def _api(path: str) -> str:
    return f"{config.WP_SITE_URL.rstrip('/')}/wp-json/slow7/v1/push/{path}"


def fetch_subscriptions() -> list[dict]:
    """워드프레스에 저장된 구독 목록을 가져온다."""
    r = requests.get(_api("list"), auth=_wp_auth(), timeout=TIMEOUT)
    r.raise_for_status()
    return r.json().get("subscriptions", [])


def prune(endpoints: list[str]) -> int:
    """만료된 구독을 워드프레스에서 삭제한다."""
    if not endpoints:
        return 0
    r = requests.delete(
        _api("prune"),
        auth=_wp_auth(),
        json={"endpoints": endpoints},
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    return int(r.json().get("deleted", 0))


def send_new_post(title: str, url: str, body: str = "") -> dict:
    """새 글 알림을 전 구독자에게 발송.

    반환: {"sent": 성공수, "failed": 실패수, "pruned": 정리된 만료구독수}
    설정이 없거나 구독자가 없으면 조용히 0 을 반환한다(발행을 막지 않는다).
    """
    priv = os.getenv("VAPID_PRIVATE_KEY", "")
    subject = os.getenv("VAPID_SUBJECT", "")
    if not priv or not subject:
        print("[push] VAPID 미설정 → 발송 생략")
        return {"sent": 0, "failed": 0, "pruned": 0}

    try:
        from pywebpush import WebPushException, webpush
    except ImportError:
        print("[push] pywebpush 미설치 → 발송 생략 (pip install pywebpush)")
        return {"sent": 0, "failed": 0, "pruned": 0}

    try:
        subs = fetch_subscriptions()
    except Exception as e:  # 구독 조회 실패가 발행을 막으면 안 된다
        print(f"[push] 구독 목록 조회 실패(무시): {e}")
        return {"sent": 0, "failed": 0, "pruned": 0}

    if not subs:
        print("[push] 구독자 없음")
        return {"sent": 0, "failed": 0, "pruned": 0}

    payload = json.dumps(
        {"title": title, "body": body or "새 글이 올라왔어. 읽어보자!", "url": url},
        ensure_ascii=False,
    )

    sent = failed = 0
    dead: list[str] = []
    for s in subs:
        info = {
            "endpoint": s["endpoint"],
            "keys": {"p256dh": s["p256dh"], "auth": s["auth"]},
        }
        try:
            webpush(
                subscription_info=info,
                data=payload,
                vapid_private_key=priv,
                vapid_claims={"sub": subject},
                timeout=TIMEOUT,
            )
            sent += 1
        except WebPushException as e:
            code = getattr(e.response, "status_code", None)
            if code in _GONE:
                dead.append(s["endpoint"])  # 구독 해지·만료 → 정리 대상
            else:
                failed += 1
                print(f"[push] 발송 실패({code}): {str(e)[:120]}")
        except Exception as e:
            failed += 1
            print(f"[push] 발송 오류(무시): {str(e)[:120]}")

    pruned = 0
    if dead:
        try:
            pruned = prune(dead)
        except Exception as e:
            print(f"[push] 만료 구독 정리 실패(무시): {e}")

    print(f"[push] 발송 {sent}건 / 실패 {failed}건 / 만료정리 {pruned}건")
    return {"sent": sent, "failed": failed, "pruned": pruned}
