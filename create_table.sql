-- Supabase SQL Editor에서 실행
CREATE TABLE cafe_posts (
  id          BIGSERIAL PRIMARY KEY,
  title       TEXT NOT NULL,
  author      TEXT NOT NULL,
  written_at  TEXT,
  post_url    TEXT UNIQUE NOT NULL,
  crawled_at  TIMESTAMPTZ DEFAULT NOW()
);

-- 상위 20명 작성자 조회 쿼리
-- SELECT author, COUNT(*) AS post_count
-- FROM cafe_posts
-- GROUP BY author
-- ORDER BY post_count DESC
-- LIMIT 20;

-- 수강생별 메모 테이블
CREATE TABLE author_memos (
  author     TEXT PRIMARY KEY,
  memo       TEXT CHECK (char_length(memo) <= 500),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);
