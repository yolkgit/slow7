# 슬로우7 (Slow7) Threads 자동 운영 봇

> 7분 페이스로 극강의 효율적인 운동효과. 슬로우조깅 정보를 마모루 말투로 매일 3번, 24/7 자동으로 운영하는 스레드 봇.

## 기능

- 🕗 **매일 3회 자동 게시** — 아침(07:00) / 점심(12:00) / 저녁(19:00) KST. 각 시간대 다른 톤·각도.
- 🥊 **마모루 말투** — "더파이팅" 마모루 같은 활기찬 반말로 슬로우조깅 지식 전달.
- 🖼 **카드뉴스 자동 생성** — 글에 어울리는 1080×1080 PNG 카드 이미지 (Pillow).
- 💬 **댓글 자동 답글** — 30분마다 미답글 댓글 폴링해서 자동 응답.
- 🔎 **트렌드 검색** — Threads 키워드 검색으로 최신 흐름 반영 (옵션).
- 🔄 **토큰 자동 갱신** — 60일짜리 long-lived 토큰을 매주 자동 refresh.
- ☁️ **GitHub Actions 무료 호스팅** — PC 꺼져있어도 동작.

## 빠른 시작

1. **셋업 가이드** — [SETUP.md](SETUP.md) 를 처음부터 끝까지 따라가면 된다 (약 40~60분).
2. 셋업이 끝나면 코드 수정 없이 그냥 돌아간다.

## 구조

```
slow7/
├── .github/workflows/
│   ├── post.yml              # 매일 3회 cron 게시
│   ├── reply.yml             # 30분마다 답글 봇
│   └── refresh_token.yml     # 주 1회 토큰 갱신
├── src/
│   ├── config.py             # env 로딩
│   ├── threads_client.py     # Threads Graph API 래퍼
│   ├── writer.py             # Claude로 마모루 말투 글 생성
│   ├── card_generator.py     # 카드뉴스 PNG 생성
│   ├── reply_bot.py          # 댓글 폴링 + 자동 답글
│   ├── search.py             # 키워드 검색 (트렌드 인사이트)
│   ├── topics.py             # 시간대별 슬로우조깅 토픽 풀
│   └── db.py                 # SQLite 이력 관리
├── scripts/
│   ├── post.py               # prepare / publish / oneshot
│   ├── reply.py              # 답글 봇 진입점
│   ├── setup_check.py        # 환경 점검
│   └── preview_card.py       # 카드 디자인 미리보기
├── assets/logo.png           # 슬로우7 로고
├── posted_media/             # 생성된 카드 이미지 (git에서 raw URL로 서빙)
├── requirements.txt
├── .env.example
└── SETUP.md
```

## 토픽 추가/수정

`src/topics.py` 의 리스트에 `Topic(...)` 한 줄 추가하면 된다. 키만 고유하게 줘.

## 톤 조정

`src/writer.py` 의 `SYSTEM_PROMPT` 를 수정. 더 거칠게 / 더 친근하게 / 다른 캐릭터 톤으로 바꾸기 쉽다.

## 라이선스

개인 프로젝트. 자유 사용.
