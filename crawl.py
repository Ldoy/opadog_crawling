import os
import time
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright
from supabase import create_client

load_dotenv()

NAVER_ID = os.environ["NAVER_ID"]
NAVER_PW = os.environ["NAVER_PW"]
SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]

CAFE_ID = "31706186"
MENU_ID = "5"
BOARD_URL = f"https://cafe.naver.com/f-e/cafes/{CAFE_ID}/menus/{MENU_ID}"


def login(page):
    page.goto("https://nid.naver.com/nidlogin.login?mode=form")
    page.wait_for_load_state("networkidle")

    page.evaluate(f"document.querySelector('#id').value = '{NAVER_ID}'")
    page.evaluate(f"document.querySelector('#pw').value = '{NAVER_PW}'")
    page.click(".btn_login")
    page.wait_for_load_state("networkidle")
    time.sleep(2)


def get_frame(page):
    for frame in page.frames:
        if "cafe_main" in (frame.name or "") or "ArticleList" in (frame.url or ""):
            return frame
    for frame in page.frames:
        if "cafe.naver.com" in (frame.url or "") and frame != page.main_frame:
            return frame
    return page


def parse_posts(frame):
    posts = []
    try:
        rows = frame.query_selector_all("#cafe_content > div.article-board > table > tbody > tr")
        for row in rows:
            try:
                link_el = row.query_selector("a.article")
                title = link_el.inner_text().strip() if link_el else ""
                href = link_el.get_attribute("href") if link_el else ""
                if href and not href.startswith("http"):
                    href = "https://cafe.naver.com" + href

                author_el = row.query_selector("span.nickname")
                author = author_el.inner_text().strip() if author_el else ""

                date_el = row.query_selector("td.td_normal.type_date")
                written_at = date_el.inner_text().strip() if date_el else ""

                if title and author:
                    posts.append({
                        "title": title,
                        "author": author,
                        "written_at": written_at,
                        "post_url": href,
                    })
            except Exception as e:
                print(f"  행 파싱 오류: {e}")
                continue
    except Exception as e:
        print(f"  목록 파싱 오류: {e}")

    return posts


def crawl_all_pages(page):
    all_posts = []
    page_num = 1

    while True:
        url = f"{BOARD_URL}?page={page_num}"
        print(f"  크롤링 중: {page_num} 페이지")
        page.goto(url)
        page.wait_for_load_state("networkidle")
        time.sleep(1.5)

        frame = get_frame(page)
        posts = parse_posts(frame)
        print(f"    → {len(posts)}개 게시글 수집")

        if not posts:
            print(f"  {page_num} 페이지 게시글 없음 → 종료")
            break

        all_posts.extend(posts)
        page_num += 1

    return all_posts


def save_to_supabase(posts):
    client = create_client(SUPABASE_URL, SUPABASE_KEY)

    KST = timezone(timedelta(hours=9))
    now_kst = datetime.now(KST).isoformat()

    seen = set()
    unique_posts = []
    for p in posts:
        if p["post_url"] and p["post_url"] not in seen:
            seen.add(p["post_url"])
            unique_posts.append({**p, "crawled_at": now_kst})

    print(f"\n총 {len(unique_posts)}개 저장 시작...")

    batch_size = 100
    success = 0
    for i in range(0, len(unique_posts), batch_size):
        batch = unique_posts[i:i + batch_size]
        try:
            client.table("cafe_posts").upsert(batch, on_conflict="post_url").execute()
            success += len(batch)
            print(f"  {success}/{len(unique_posts)} 저장 완료")
        except Exception as e:
            print(f"  저장 오류 (batch {i}): {e}")

    print(f"\n완료: {success}개 저장됨")


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()

        print("네이버 로그인 중...")
        login(page)
        print("로그인 완료")

        print("\n크롤링 시작...")
        all_posts = crawl_all_pages(page)
        print(f"\n총 {len(all_posts)}개 게시글 수집 완료")

        browser.close()

    save_to_supabase(all_posts)


if __name__ == "__main__":
    main()
