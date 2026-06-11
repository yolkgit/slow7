# 슬로우7 워드프레스 블로그 자동 발행 셋업 가이드

> Threads에서 워드프레스 블로그로 전환. 자동 발행이 100% 안전하고(정지 위험 0), 구글 검색 유입 + 애드센스·쿠팡 제휴로 수익화. 셋업 약 1시간.

---

## 0. 전체 그림

```
GitHub Actions (또는 cron-job.org) — 하루 1회
   ↓
Claude가 SEO 블로그 글 생성 (제목/본문HTML/메타/태그/썸네일)
   ↓
WordPress REST API로 자동 발행
   ↓
구글 인덱싱 → 검색 유입 → 애드센스 + 쿠팡 제휴 수익
```

**필요한 것:**
1. 워드프레스 사이트 (호스팅)
2. Application Password (워드프레스 내장 인증)
3. Claude API 키 (이미 있음)
4. GitHub 리포 (이미 있음)

---

## 1. 호스팅 선택 + 워드프레스 설치

### 추천: 카페24 (한국, 저렴, 한국어)

1. https://www.cafe24.com → **호스팅** → **워드프레스 호스팅**
2. **절약형** (월 약 1,100원) 선택 → 신청
3. 도메인: 일단 제공되는 무료 주소(`아이디.cafe24.com`)로 시작 가능. 나중에 `.co.kr` 도메인 연결 (연 1.5만원)
4. 신청 시 **워드프레스 자동 설치** 옵션 체크
5. 설치 완료되면 `http://아이디.cafe24.com/wp-admin` 으로 관리자 로그인

### 대안: Hostinger (해외, 빠름)
1. https://www.hostinger.com → **WordPress Hosting** → Single ($2~3/월)
2. Auto Installer로 워드프레스 설치
3. 무료 도메인 1년 제공

### 설치 후 필수 설정
1. 관리자 로그인 → **설정 → 고유주소(Permalinks)**
2. **글 이름(Post name)** 선택 → 저장 (SEO 친화 URL)
3. **설정 → 일반**에서 사이트 제목 "슬로우7", 태그라인 "7분 페이스로 극강의 효율" 설정

---

## 2. Application Password 발급 (자동 발행 인증)

> Application Password는 워드프레스 5.6+ 내장 기능. 비밀번호 노출 없이 API 접근용.

1. 워드프레스 관리자 → **사용자(Users) → 프로필(Profile)**
2. 페이지 맨 아래로 스크롤 → **Application Passwords** 섹션
3. **New Application Password Name**에 `slow7-auto` 입력 → **Add New Application Password**
4. 화면에 표시되는 비밀번호 복사 (형식: `abcd EFGH ijkl MNOP qrst UVWX`, 공백 포함)
   - ⚠️ 한 번만 표시됨. 메모장에 복사
   - ⚠️ 공백 포함해서 그대로 사용

### Application Passwords 섹션이 안 보이면?
- HTTPS가 아니면 숨겨질 수 있음 → 호스팅의 무료 SSL 켜기
- 또는 보안 플러그인(Wordfence 등)이 막는 경우 → 일시 해제 후 발급

---

## 3. 로컬에서 연결 테스트 (선택, 권장)

PowerShell에서:

```powershell
cd C:\Users\DH201-pc\Desktop\slow7
pip install -r requirements.txt
copy .env.example .env
notepad .env
```

`.env`에 입력:
```
ANTHROPIC_API_KEY=sk-ant-...
WP_SITE_URL=https://아이디.cafe24.com
WP_USERNAME=관리자아이디
WP_APP_PASSWORD=abcd EFGH ijkl MNOP qrst UVWX
WP_DEFAULT_CATEGORY=슬로우조깅
WP_POST_STATUS=draft
DRY_RUN=false
```

> 💡 처음엔 `WP_POST_STATUS=draft`로 시작 → 글이 초안으로만 저장돼서 확인 후 직접 공개. 익숙해지면 `publish`로.

연결 점검:
```powershell
python -m scripts.wp_check
```
`✅ 연결 성공` 뜨면 OK.

첫 글 발행 테스트:
```powershell
python -m scripts.publish_blog
```
→ 워드프레스 관리자 **글(Posts)** 에서 초안 확인

---

## 4. GitHub Secrets 등록 (클라우드 자동 발행)

리포 → **Settings → Secrets and variables → Actions → New repository secret**

| Secret 이름 | 값 |
|---|---|
| `ANTHROPIC_API_KEY` | (이미 등록돼 있음) |
| `WP_SITE_URL` | `https://아이디.cafe24.com` |
| `WP_USERNAME` | 워드프레스 관리자 아이디 |
| `WP_APP_PASSWORD` | Application Password (공백 포함) |

(옵션) **Variables** 탭:
| Variable | 값 |
|---|---|
| `WP_POST_STATUS` | `draft` (테스트) → `publish` (실서비스) |
| `WP_DEFAULT_CATEGORY` | `슬로우조깅` |
| `DRY_RUN` | `true`(테스트) / `false`(실발행) |

---

## 5. 첫 자동 발행 테스트

1. 리포 → **Actions** → **Slow7 Blog Auto Publish**
2. **Run workflow** → topic_key 비워두고 실행
3. **Publish blog post** 단계 로그 확인:
   ```
   [blog] 토픽: e_science_fat (지방산 산화 메커니즘)
   [blog] 제목: 슬로우조깅 효과, 7분 페이스가 살 빼는 진짜 이유
   [blog] ✅ 발행 완료: https://아이디.cafe24.com/slow-jogging-fat-burn
   ```
4. 그 링크 들어가서 글 확인

---

## 6. 정기 자동 발행

기본 설정은 **하루 1회 (오전 8:40 KST)** 자동 발행 (`.github/workflows/blog.yml`).

### GitHub schedule이 지연되면 (이전 Threads 때처럼)
cron-job.org로 정확한 시각 트리거:
- URL: `https://api.github.com/repos/yolkgit/slow7/actions/workflows/blog.yml/dispatches`
- Body: `{"ref":"main"}`
- Header: `Authorization: Bearer <GitHub PAT>`
- Schedule: 매일 원하는 시각

> 블로그는 발행 빈도가 낮아서(하루 1회) GitHub schedule 지연도 크게 문제 안 됨. 글이 몇 시에 올라가든 검색 유입엔 영향 없음.

---

## 7. 수익화 단계 (글 쌓인 후)

### 1단계 — 쿠팡 파트너스 (지금 가능)
1. https://partners.coupang.com 가입
2. 러닝화, 무릎보호대, 폼롤러 등 제휴 링크 생성
3. 관련 글에 자연스럽게 삽입 (수동 — 글마다 맞는 상품)

### 2단계 — 구글 애드센스 (글 15~20개 + 트래픽 쌓인 후)
1. https://adsense.google.com 신청
2. 승인되면 자동 광고 코드 삽입 → 방문자당 수익

### 3단계 — 자체 상품 (트래픽 궤도 오른 후)
- 슬로우조깅 PDF 가이드, 4주 챌린지 프로그램 등

---

## 8. 운영 모니터링

| 보는 곳 | 확인 |
|---|---|
| 리포 Actions 탭 | 자동 발행 성공 여부 |
| 워드프레스 관리자 → 글 | 실제 발행된 글 |
| Google Search Console | 검색 노출/유입 (사이트 등록 필수) |
| Google Analytics | 방문자 추적 |

### 꼭 할 것 — Google Search Console 등록
1. https://search.google.com/search-console
2. 사이트 URL 등록 + 소유 확인
3. 사이트맵 제출: `https/아이디.cafe24.com/sitemap.xml` (또는 Yoast SEO 플러그인)
→ 구글이 글을 빨리 인덱싱해서 검색 유입 시작

---

## 9. 추천 워드프레스 플러그인 (SEO)

관리자 → **플러그인 → 새로 추가**:
- **Yoast SEO** 또는 **Rank Math** — 메타태그, 사이트맵 자동
- 우리 자동 발행이 meta_description을 보내지만, Yoast가 있으면 더 정교한 SEO 제어 가능

---

## 정리 — 셋업 순서

1. ✅ 호스팅 가입 + 워드프레스 설치 (카페24 추천)
2. ✅ 고유주소 "글 이름" 설정
3. ✅ Application Password 발급
4. ✅ (선택) 로컬 `.env` 테스트 — `wp_check` → `publish_blog`
5. ✅ GitHub Secrets 3개 등록 (WP_SITE_URL / WP_USERNAME / WP_APP_PASSWORD)
6. ✅ Actions에서 첫 발행 테스트 (draft로)
7. ✅ Google Search Console 등록
8. ✅ 익숙해지면 WP_POST_STATUS=publish 로 자동 공개

천천히, 7분 페이스로. 이번엔 정지당할 걱정 없이 쭉 간다 🏃‍♂️🔥
