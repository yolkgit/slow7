"""슬로우7 카드뉴스 이미지 생성.

브랜드 톤: 검정 배경 + 흰색 텍스트 + 라임 그린 포인트 컬러 (#C8FF3C).
출력: 1080x1080 PNG.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable

from PIL import Image, ImageDraw, ImageFont

from . import config

CANVAS = 1080
BG = (0, 0, 0)
FG = (255, 255, 255)
ACCENT = (200, 255, 60)  # 라임 그린

# 한글 폰트 후보 — 단일 .ttf를 .ttc보다 우선 (Pillow 호환성)
FONT_CANDIDATES: list[str] = [
    # Ubuntu — fonts-nanum (단일 ttf, Pillow 호환성 최고)
    "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf",
    "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
    "/usr/share/fonts/truetype/nanum/NanumBarunGothicBold.ttf",
    "/usr/share/fonts/truetype/nanum/NanumBarunGothic.ttf",
    # Ubuntu — fonts-noto-cjk (.ttc, index 지정 필요)
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    # Windows 로컬 테스트용
    "C:/Windows/Fonts/malgunbd.ttf",
    "C:/Windows/Fonts/malgun.ttf",
    # macOS
    "/System/Library/Fonts/AppleSDGothicNeo.ttc",
]


_FONT_LOGGED: set[str] = set()


def _load_font(size: int) -> ImageFont.FreeTypeFont:
    for path in FONT_CANDIDATES:
        if not os.path.exists(path):
            continue
        try:
            # .ttc는 index=0 명시 (한국어 글리프 포함된 0번 사용)
            if path.endswith(".ttc"):
                font = ImageFont.truetype(path, size=size, index=0)
            else:
                font = ImageFont.truetype(path, size=size)
            if path not in _FONT_LOGGED:
                print(f"[card_generator] ✅ 사용 폰트: {path}")
                _FONT_LOGGED.add(path)
            return font
        except OSError as e:
            print(f"[card_generator] ⚠️  {path} 로드 실패: {e}")
            continue
    print("[card_generator] ❌ 한글 폰트 찾기 실패. 모든 후보:")
    for p in FONT_CANDIDATES:
        print(f"  - {p}: {'있음' if os.path.exists(p) else '없음'}")
    return ImageFont.load_default()


def _measure(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont) -> tuple[int, int]:
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0], bbox[3] - bbox[1]


def _wrap(text: str, draw: ImageDraw.ImageDraw, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    """한글 기준 문자 단위 줄바꿈."""
    lines: list[str] = []
    cur = ""
    for ch in text:
        if ch == "\n":
            lines.append(cur)
            cur = ""
            continue
        test = cur + ch
        w, _ = _measure(draw, test, font)
        if w > max_width and cur:
            lines.append(cur)
            cur = ch
        else:
            cur = test
    if cur:
        lines.append(cur)
    return lines


def generate(card_title: str, card_subtitle: str, slot: str, out_path: Path) -> Path:
    """카드 이미지를 생성해 out_path에 저장하고 경로 반환."""
    out_path.parent.mkdir(parents=True, exist_ok=True)

    img = Image.new("RGB", (CANVAS, CANVAS), BG)
    draw = ImageDraw.Draw(img)

    # 상단 로고
    if config.LOGO_PATH.exists():
        logo = Image.open(config.LOGO_PATH).convert("RGBA")
        # 로고는 가로 360px 정도로 리사이즈
        logo_w = 360
        ratio = logo_w / logo.width
        logo_h = int(logo.height * ratio)
        logo = logo.resize((logo_w, logo_h), Image.LANCZOS)
        img.paste(logo, ((CANVAS - logo_w) // 2, 60), logo)

    # 슬롯 라벨 (작은 라임색 텍스트)
    slot_label = {"morning": "MORNING / 아침", "noon": "NOON / 점심", "evening": "EVENING / 저녁"}.get(slot, "")
    if slot_label:
        label_font = _load_font(28)
        w, _ = _measure(draw, slot_label, label_font)
        draw.text(((CANVAS - w) // 2, 480), slot_label, font=label_font, fill=ACCENT)

    # 큰 제목
    title_font = _load_font(96)
    title_lines = _wrap(card_title, draw, title_font, CANVAS - 160)
    y = 560
    for line in title_lines:
        w, h = _measure(draw, line, title_font)
        draw.text(((CANVAS - w) // 2, y), line, font=title_font, fill=FG)
        y += h + 30

    # 라임 라인 (제목 아래로 충분히 띄워서)
    y += 28
    draw.rectangle([(CANVAS // 2 - 80, y), (CANVAS // 2 + 80, y + 6)], fill=ACCENT)
    y += 52

    # 부제목
    sub_font = _load_font(44)
    sub_lines = _wrap(card_subtitle, draw, sub_font, CANVAS - 200)
    for line in sub_lines:
        w, h = _measure(draw, line, sub_font)
        draw.text(((CANVAS - w) // 2, y), line, font=sub_font, fill=FG)
        y += h + 6

    # 하단 슬로건
    slogan_font = _load_font(30)
    slogan = "BURN FAT AT A 7 MIN PACE."
    w, h = _measure(draw, slogan, slogan_font)
    draw.text(((CANVAS - w) // 2, CANVAS - 80), slogan, font=slogan_font, fill=ACCENT)

    img.save(out_path, "PNG", optimize=True)
    return out_path


def public_url_for(filename: str) -> str | None:
    """GitHub raw URL 빌드. 리포지토리 정보 없으면 None."""
    if not config.GITHUB_REPO:
        return None
    return f"https://raw.githubusercontent.com/{config.GITHUB_REPO}/{config.GITHUB_BRANCH}/posted_media/{filename}"
