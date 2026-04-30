# 네이버 카페 게시글 크롤링 스크립트

## 목적
네이버 카페 특정 게시판의 **전체 게시글**을 수집해 Supabase에 저장하고,  
**상위 20명 작성자**를 확인한다.

---

## 크롤링 대상
- **게시판 URL**: https://cafe.naver.com/f-e/cafes/31706186/menus/5
- **수집 항목**: 제목, 작성자, 작성일, 게시글 링크
- **수집 범위**: 1페이지 ~ 끝 페이지 (전체)

---

## 파일 구조

```
naver-cafe-post-crawling/
├── crawl.py          ← 메인 크롤링 스크립트
├── .env              ← 인증 정보 (직접 입력 필요)
├── requirements.txt  ← Python 패키지 목록
├── create_table.sql  ← Supabase 테이블 생성 SQL
└── README.md         ← 이 파일
```

---

## 사전 준비

### 1. Python 3 설치 확인
```bash
python3 --version
```

### 2. 패키지 설치
```bash
pip install -r requirements.txt
playwright install chromium
```

### 3. .env 파일 작성
`.env` 파일을 열어 아래 4개 값을 채운다.

```
NAVER_ID=네이버아이디
NAVER_PW=네이버비밀번호
SUPABASE_URL=https://xxxx.supabase.co
SUPABASE_KEY=your-anon-key
```

> Supabase URL과 Key는 Supabase 대시보드 → Project Settings → API에서 확인

### 4. Supabase 테이블 생성
Supabase 대시보드 → SQL Editor에서 `create_table.sql` 내용을 실행한다.

```sql
CREATE TABLE cafe_posts (
  id          BIGSERIAL PRIMARY KEY,
  title       TEXT NOT NULL,
  author      TEXT NOT NULL,
  written_at  TEXT,
  post_url    TEXT UNIQUE NOT NULL,
  crawled_at  TIMESTAMPTZ DEFAULT NOW()
);
```

---

## 실행

```bash
python crawl.py
```

실행하면 순서대로 진행된다:
1. 브라우저 창이 열리며 네이버 로그인
2. 마지막 페이지 번호 자동 확인
3. 1페이지부터 끝 페이지까지 순차 크롤링
4. Supabase에 100개씩 배치 저장

> 브라우저 창이 열리는 이유: 네이버 캡차나 2차 인증이 뜰 경우 직접 처리하기 위함.  
> 문제 없이 통과되면 자동으로 진행된다.

---

## 결과 확인: 상위 20명 작성자

크롤링 완료 후 Supabase SQL Editor에서 실행:

```sql
SELECT author, COUNT(*) AS post_count
FROM cafe_posts
GROUP BY author
ORDER BY post_count DESC
LIMIT 20;
```

---

## 트러블슈팅

### 수집된 데이터가 비어있는 경우
네이버 카페 새 UI(`f-e` 형식)는 CSS 클래스명이 자주 변경된다.  
`crawl.py`의 `parse_posts()` 함수 내 셀렉터를 수정해야 할 수 있다.

브라우저 창에서 게시판 페이지를 열고 개발자 도구(F12) → Elements 탭에서  
제목/작성자/날짜 요소의 클래스명을 확인한 뒤 아래 부분을 수정한다:

```python
# crawl.py 내 parse_posts() 함수
title_el  = row.query_selector("여기를 실제 클래스명으로 수정")
author_el = row.query_selector("여기를 실제 클래스명으로 수정")
date_el   = row.query_selector("여기를 실제 클래스명으로 수정")
link_el   = row.query_selector("여기를 실제 클래스명으로 수정")
```

### 로그인 후 캡차가 뜨는 경우
브라우저 창에서 직접 캡차를 해결하면 스크립트가 자동으로 이어서 진행된다.

### 속도 조절
크롤링이 너무 빠르면 네이버에서 차단될 수 있다.  
`crawl.py` 내 `time.sleep(1.5)` 값을 높여 조절한다.
