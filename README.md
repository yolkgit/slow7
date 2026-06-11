# 슬로우7 (Slow7) — 슬로우조깅 정보 블로그 자동 발행

> 7분 페이스로 극강의 효율. 슬로우조깅 정보를 마모루 톤으로 워드프레스 블로그에 자동 발행하는 시스템.

## 현재 방향 — 워드프레스 블로그

> ⚠️ 초기엔 Threads 자동화로 시작했으나, 자동 답글 봇이 메타 정책 위반으로 계정이 정지됨.
> 자동화에 안전하고 정지 위험이 없는 **워드프레스 블로그 + SEO**로 전환.

## 기능

- 📝 **자동 글 발행** — 하루 1회, SEO 최적화된 슬로우조깅 정보 글
- 🥊 **마모루 톤** — "더파이팅" 마모루 같은 활기찬 반말, 정보는 충실하게
- 🔍 **SEO 구조** — 제목/메타디스크립션/태그/H2 소제목/슬러그 자동 생성
- 🖼 **썸네일 자동 생성** — 슬로우7 브랜드 카드 이미지를 대표 이미지로
- 📊 **성과 가중 토픽 선택** — 잘 되는 주제를 더 자주 (구글 애널리틱스 연동 예정)
- ☁️ **GitHub Actions 무료 호스팅** — PC 꺼져있어도 동작
- 🛡 **정지 위험 0** — 내 서버라 자동화 제약 없음

## 빠른 시작

**셋업 가이드** — [SETUP_WORDPRESS.md](SETUP_WORDPRESS.md) 를 따라가면 됨 (약 1시간).

## 구조

```
slow7/
├── .github/workflows/
│   └── blog.yml              # 하루 1회 자동 발행
├── src/
│   ├── config.py             # env 로딩 (WP 설정 포함)
│   ├── wordpress_client.py   # WordPress REST API (발행/미디어/분류)
│   ├── blog_writer.py        # Claude로 SEO 블로그 글 생성
│   ├── card_generator.py     # 썸네일 PNG 생성
│   ├── topics.py             # 슬로우조깅 토픽 풀 38개
│   └── db.py                 # 발행 이력 + 성과 추적
├── scripts/
│   ├── publish_blog.py       # 발행 진입점
│   └── wp_check.py           # WordPress 연결 점검
├── assets/logo.png
├── posted_media/             # 생성된 썸네일
├── requirements.txt
├── .env.example
└── SETUP_WORDPRESS.md

# 아카이브 (Threads 시절 — 더 이상 사용 안 함):
#   src/threads_client.py, src/writer.py, src/reply_bot.py,
#   src/search.py, src/growth_bot.py, scripts/post.py, scripts/reply.py 등
```

## 토픽 추가/수정

`src/topics.py` 의 리스트에 `Topic(...)` 한 줄 추가.

## 톤 조정

`src/blog_writer.py` 의 `BLOG_SYSTEM` 프롬프트 수정.

## 라이선스

개인 프로젝트.
