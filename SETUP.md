# 슬로우7 자동화 셋업 가이드

> 처음부터 끝까지 순서대로 따라가면 약 40~60분 소요. 한 번만 셋업하면 그 다음부터는 GitHub가 알아서 매일 3번 게시하고 30분마다 댓글에 자동 답글한다.

---

## 0. 한눈에 보는 전체 흐름

```
[GitHub Actions cron]
   ├─ 매일 07:00 KST → post.py prepare morning → 카드이미지 git push → publish
   ├─ 매일 12:00 KST → 동일 (noon)
   ├─ 매일 19:00 KST → 동일 (evening)
   └─ 매 30분         → reply.py (미답글 댓글에 마모루 말투 답글)

[외부 서비스 4개]
   1) Threads 앱 (인스타로 가입)
   2) Meta for Developers 콘솔 (Threads API 앱)
   3) Anthropic Console (Claude API 키)
   4) GitHub (코드 호스팅 + Actions cron)
```

---

## 1. Threads 계정 만들기

1. https://www.threads.net 접속 → **인스타그램 계정으로 로그인**
2. 이름/핸들을 슬로우7 브랜드에 맞게 설정 (예: `@slow7.crew`)
3. 프로필 사진: `assets/logo.png` 사용
4. 자기소개에 슬로건 한 줄: "7분 페이스로 극강의 효율 / 매일 아침·점심·저녁 슬로우조깅 정보"
5. **프로필을 공개**로 (비공개면 API 게시가 막힘)

---

## 2. Meta 개발자 앱 생성 + Threads API 권한 받기

### 2-1. 개발자 콘솔 진입
1. https://developers.facebook.com 접속 (Threads 가입에 쓴 페이스북/인스타 계정으로 로그인)
2. 우측 상단 **My Apps** → **Create App**
3. Use case: **Other** → 다음
4. App type: **Business** → 다음
5. 앱 이름: `Slow7 Auto` (아무거나 OK), 연락처 이메일 입력 → **Create app**

### 2-2. Threads 제품 추가
1. 만들어진 앱 대시보드에서 **Add Product** 섹션 스크롤
2. **Threads** 카드의 **Set up** 클릭
3. 좌측 메뉴 → **Use cases** → **Access the Threads API** → **Customize**

### 2-3. 권한(scope) 추가
다음 권한들을 모두 **Add** 하기:
- `threads_basic` (필수)
- `threads_content_publish` (게시용 — 필수)
- `threads_manage_replies` (답글 게시용)
- `threads_read_replies` (댓글 조회용)
- `threads_keyword_search` (옵션 — 트렌드 검색용)

### 2-4. 테스터 추가 (앱이 In Development 상태일 때 필요)
1. 좌측 메뉴 → **App roles** → **Roles** (또는 **Threads Testers**)
2. **Add Threads testers** → 본인 Threads 핸들 입력 → 초대
3. **Threads 앱에서 초대 수락** (Threads → 설정 → 계정 → 웹사이트 권한)

### 2-5. 토큰 발급

#### A. 짧은 토큰 (1시간짜리) 받기
1. 좌측 메뉴 → **Use cases** → **Access the Threads API** → **Settings**
2. 페이지 하단 **Redirect Callback URLs**에 `https://localhost/` 추가
3. **App secret**, **App ID** 메모해두기 (좌측 **Settings** → **Basic** 에서 확인)
4. 다음 URL을 브라우저에 붙여넣어 권한 동의 (`{APP_ID}` 본인 것으로 교체):
   ```
   https://threads.net/oauth/authorize?client_id={APP_ID}&redirect_uri=https://localhost/&scope=threads_basic,threads_content_publish,threads_manage_replies,threads_read_replies,threads_keyword_search&response_type=code
   ```
5. 동의 후 `https://localhost/?code=AQ...#_` 로 리다이렉트 됨. `code=` 뒤에서 `#_` 앞까지를 복사 (이게 `AUTH_CODE`)
6. 터미널/PowerShell에서 (`{APP_ID}`, `{APP_SECRET}`, `{AUTH_CODE}` 본인 것으로 교체):
   ```powershell
   curl.exe -X POST "https://graph.threads.net/oauth/access_token" `
     -d "client_id={APP_ID}" `
     -d "client_secret={APP_SECRET}" `
     -d "grant_type=authorization_code" `
     -d "redirect_uri=https://localhost/" `
     -d "code={AUTH_CODE}"
   ```
   응답에 `access_token`(짧은 토큰), `user_id` 가 있음. 둘 다 메모.

#### B. 짧은 토큰 → 장기 토큰 (60일) 교환
```powershell
curl.exe -G "https://graph.threads.net/access_token" `
  --data-urlencode "grant_type=th_exchange_token" `
  --data-urlencode "client_secret={APP_SECRET}" `
  --data-urlencode "access_token={SHORT_LIVED_TOKEN}"
```
응답의 `access_token`이 60일짜리 **장기 토큰**이다. 이걸 사용한다.

> 💡 `refresh_token.yml` 워크플로우가 매주 일요일 자동으로 갱신해서 토큰이 끊기지 않게 해준다.

---

## 3. Claude API 키 발급

1. https://console.anthropic.com 가입 (Google 로그인 가능)
2. **Plans & Billing** → 결제수단 등록 (Pay as you go, 최소 충전 $5)
3. **API keys** → **Create Key** → 이름 `slow7` → **Create**
4. 표시되는 키를 **꼭 복사** (다시 못 봄. 형식: `sk-ant-api03-...`)

> 💰 예상 비용: Haiku 4.5 기준 글 1개당 약 $0.001~0.003. 하루 3개 + 답글 10개 = 월 약 $1~3.

---

## 4. GitHub 리포 만들고 코드 올리기

### 4-1. 새 리포 생성
1. https://github.com → **+** → **New repository**
2. 이름: `slow7` (또는 원하는 이름)
3. **Private** 선택 (토큰을 다루기 때문에 비공개 추천)
4. **Create repository**

### 4-2. 로컬에서 푸시 (PowerShell)
```powershell
cd C:\Users\DH201-pc\Desktop\slow7
git init -b main
git add .
git commit -m "feat: initial slow7 auto-poster"
git remote add origin https://github.com/{your-username}/slow7.git
git push -u origin main
```

### 4-3. GitHub Secrets 등록
리포 페이지 → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**

| Secret 이름 | 값 |
|---|---|
| `ANTHROPIC_API_KEY` | sk-ant-api03-... (3단계에서 받은 키) |
| `THREADS_ACCESS_TOKEN` | 2-5-B에서 받은 60일 장기 토큰 |
| `THREADS_USER_ID` | 2-5-A 응답의 `user_id` 숫자 |

(옵션) **Variables** 탭에서:
| Variable 이름 | 값 |
|---|---|
| `DRY_RUN` | `true` (테스트 중) / `false` (실서비스) |
| `ANTHROPIC_MODEL` | `claude-haiku-4-5-20251001` (기본) 또는 `claude-sonnet-4-6` (품질 더 좋게) |

### 4-4. Actions 권한 확인
리포 **Settings** → **Actions** → **General** → **Workflow permissions**
→ **Read and write permissions** 선택 → **Save**
(워크플로우가 카드 이미지를 git push하기 위해 필요)

---

## 5. 첫 테스트

### 5-1. DRY_RUN으로 워크플로우 한번 돌려보기
1. GitHub 리포 → **Actions** 탭
2. **Slow7 Auto Post** 워크플로우 클릭
3. 우측 **Run workflow** → slot: `morning` → **Run workflow**
4. 실행 로그에서 생성된 글이 마음에 드는지 확인 (DRY_RUN=true면 실제 게시 X)

### 5-2. 실제 게시 활성화
1. **Settings → Variables**에서 `DRY_RUN` 을 `false` 로 변경 (또는 삭제)
2. 다시 **Run workflow** → 진짜로 Threads에 글이 올라가는지 확인

---

## 6. 운영 중 모니터링

### 일상적으로 보는 곳
- **GitHub Actions 탭** : cron 실행 성공/실패 로그
- **Threads 본인 프로필** : 실제 올라간 글
- 리포 `posted_media/` : 자동 생성된 카드 이미지들
- 리포 `slow7.db` (옵션) : SQLite로 게시/답글 이력 추적

### 자주 만나는 이슈
| 증상 | 원인/해결 |
|---|---|
| Threads 403 / token invalid | 60일 지나 만료. `refresh_token.yml` 워크플로우 수동 실행 → 새 토큰을 Secret에 갱신 |
| 카드 이미지가 안 붙고 텍스트만 | raw URL이 아직 CDN 반영 전. 워크플로우의 `sleep 25` 를 `sleep 40` 정도로 늘려보기 |
| 답글 봇이 댓글 못 가져옴 | `threads_manage_replies` / `threads_read_replies` 권한 누락. 2-3 단계 재확인 |
| 같은 주제가 반복됨 | `src/topics.py` 의 토픽 풀에 새 항목 추가 |
| 글이 너무 광고스럽다 | `src/writer.py` 의 `SYSTEM_PROMPT` 수정 → 더 강한 마모루 톤 예시 추가 |

### 토픽 풀 확장하는 법
`src/topics.py` 의 `MORNING / NOON / EVENING` 리스트에 `Topic(...)` 객체를 추가하기만 하면 됨. 키만 고유하면 됨.

---

## 7. 로컬에서 미리 돌려보기 (선택)

```powershell
cd C:\Users\DH201-pc\Desktop\slow7
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
# .env 열어서 키들 채우기 + DRY_RUN=true 로 시작

# 환경 점검
python -m scripts.setup_check

# 카드 이미지 미리보기 (posted_media/preview_*.png)
python -m scripts.preview_card

# 글 생성+게시 한방에 (DRY_RUN=true 면 콘솔만 출력)
python -m scripts.post oneshot morning

# 답글 봇 한 사이클 돌리기
python -m scripts.reply
```

---

## 8. 끝!

이제 PC를 꺼도 GitHub가 알아서 매일 3번 글을 올리고 댓글에 답을 단다. 가끔 Actions 탭만 확인해서 빨간색이 떠있으면 로그 보고 고치면 된다. 🔥
