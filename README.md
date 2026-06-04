# 오파독 카페 게시글 크롤링 & 대시보드

## 목적
네이버 카페(오파독) 특정 게시판의 게시글을 크롤링해 Supabase에 저장하고, Streamlit 대시보드로 조회한다.

- **대시보드**: https://opadogcrawling.streamlit.app
- **게시판**: https://cafe.naver.com/f-e/cafes/31706186/menus/5

---

## 파일 구조

```
opadog_crawling/
├── crawl.py          ← 크롤링 스크립트 (Playwright, 로컬/서버 실행)
├── api_server.py     ← FastAPI 트리거 서버 (Hetzner 포트 8006)
├── dashboard.py      ← Streamlit 대시보드
├── .env              ← 인증 정보 (git 제외)
├── requirements.txt  ← 대시보드용 패키지 (playwright 제외)
├── create_table.sql  ← Supabase 테이블 생성 SQL
└── README.md
```

---

## 환경변수

| 변수 | 용도 | 위치 |
|------|------|------|
| `NAVER_ID` | 네이버 로그인 ID | .env (crawl.py 전용) |
| `NAVER_PW` | 네이버 로그인 PW | .env (crawl.py 전용) |
| `SUPABASE_URL` | Supabase 프로젝트 URL | .env / Streamlit Secrets |
| `SUPABASE_KEY` | Supabase anon key | .env / Streamlit Secrets |
| `NTFY_TOPIC` | ntfy 알림 토픽 (기본값: `opadog-crawl`) | .env 선택사항 |
| `HEADLESS` | 브라우저 headless 여부 (기본값: `true`) | .env 선택사항 |
| `CRAWL_API_URL` | 수동 크롤링 API URL | Streamlit Secrets 전용 |
| `CRAWL_API_TOKEN` | 수동 크롤링 API 토큰 | Streamlit Secrets 전용 |

---

## 로컬 실행

```bash
# 1. 패키지 설치 (최초 1회)
pip install playwright supabase python-dotenv
playwright install chromium

# 2. .env 파일 작성
cp .env.example .env  # NAVER_ID, NAVER_PW, SUPABASE_URL, SUPABASE_KEY 입력

# 3. 크롤링 실행 (브라우저 창 열림)
python3 crawl.py

# 4. 대시보드 실행
streamlit run dashboard.py
```

---

## Hetzner 서버 설정 (5.223.71.64)

### 경로
- 크롤링: `/root/naver-cafe-crawling/`

### 자동 크롤링 (cron)
```
0 0 * * * cd /root/naver-cafe-crawling && python3 crawl.py >> /root/naver-cafe-crawling/crawl.log 2>&1
```
> ⚠️ 서버 cron은 UTC 기준. `CRON_TZ=Asia/Seoul` 미동작 확인됨.
> KST 9시 = UTC 0시 → `0 0 * * *` 사용

### API 서버 (pm2: crawl-api, 포트 8006)
- `POST /crawl` — 크롤링 트리거 (Bearer 토큰 인증)
- `GET /status` — 크롤링 상태 조회 (`running` / `done` / `error` / `idle`)

### 파일 업로드
```bash
scp -i ~/.ssh/hetzner_iris crawl.py api_server.py root@5.223.71.64:/root/naver-cafe-crawling/

# api_server 재시작
ssh -i ~/.ssh/hetzner_iris root@5.223.71.64 \
  "export PATH='/root/.local/share/fnm/node-versions/v22.22.2/installation/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:\$PATH' && pm2 restart crawl-api"
```

---

## Streamlit Cloud 배포

1. GitHub push → 자동 재배포
2. Secrets 설정: share.streamlit.io → 앱 → Settings → Secrets

```toml
SUPABASE_URL = "https://xxxx.supabase.co"
SUPABASE_KEY = "sb_publishable_..."
CRAWL_API_URL = "http://5.223.71.64:8006/crawl"
CRAWL_API_TOKEN = "your-token"
```

---

## 크롤링 동작 방식

1. 로그인: Playwright로 네이버 ID/PW 주입 → 로그인
2. **신규 게시글 수집**: 크롤 전 DB 기존 URL 전체 로드 → 페이지를 순회하며 중복은 건너뛰고 신규만 수집, **한 페이지 전체가 신규 0개일 때 종료** (상단 고정 공지가 매 페이지에 떠도 안전)
3. 저장: `upsert(on_conflict="post_url")` — 새 글 추가, 기존 글 업데이트
4. 완료 시: ntfy 알림 + `crawl_status.json` 업데이트

### CSS 셀렉터
- 행: `#cafe_content > div.article-board > table > tbody > tr`
- 제목+링크: `a.article`
- 작성자: `span.nickname`
- 작성일: `td.td_normal.type_date`

---

## 트러블슈팅

| 증상 | 원인 | 해결 |
|------|------|------|
| 게시글 0개 수집 | CSS 셀렉터 불일치 | 개발자도구로 실제 클래스명 확인 |
| ntfy 제목 깨짐 | URL-encode 방식 사용 | JSON body 방식으로 변경 |
| Streamlit Cloud 빌드 실패 | requirements.txt에 playwright 포함 | playwright는 로컬/서버 전용, 제외 |
| Supabase Invalid API key | supabase 패키지 버전 낮음 | `supabase>=2.10.0` 사용 |
| cron 엉뚱한 시간에 실행 | CRON_TZ 미동작 | UTC로 직접 변환해서 등록 |
| 대시보드에 중복 게시글 | 같은 글이 page=1, page=8로 다른 URL에 중복 저장 | `href.split("?")[0]`으로 쿼리파라미터 제거 후 저장 |
| 게시글수가 특정 값에 계속 고정 (예: 223개) | 페이지 최상단 고정 공지(📢)가 항상 DB에 존재 → "첫 중복 시 즉시 종료" 로직이 공지에서 멈춰 바로 아래 신규 글 누락 | 첫 중복에서 멈추지 않고 중복은 건너뛰며, 한 페이지 전체 신규 0개일 때만 종료 |
