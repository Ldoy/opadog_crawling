import os
import time
import json
import urllib.request
import urllib.parse
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
NTFY_TOPIC = os.environ.get("NTFY_TOPIC", "opadog-crawl")
HEADLESS = os.environ.get("HEADLESS", "true").lower() != "false"
STATUS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "crawl_status.json")


def write_status(state: str, message: str = ""):
    try:
        with open(STATUS_FILE, "w") as f:
            json.dump({"state": state, "message": message, "updated_at": datetime.now().isoformat()}, f)
    except Exception:
        pass


def notify(title, message, priority="default"):
    try:
        payload = json.dumps({"topic": NTFY_TOPIC, "title": title, "message": message, "priority": 3}).encode("utf-8")
        req = urllib.request.Request(
            "https://ntfy.sh",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        urllib.request.urlopen(req, timeout=10)
    except Exception as e:
        print(f"ntfy 알림 실패: {e}")


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


def load_existing_urls():
    client = create_client(SUPABASE_URL, SUPABASE_KEY)
    res = client.table("cafe_posts").select("post_url").execute()
    return {row["post_url"] for row in res.data}


def crawl_all_pages(page):
    existing_urls = load_existing_urls()
    print(f"  기존 DB 게시글 수: {len(existing_urls)}개")

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

        stopped = False
        for post in posts:
            if post["post_url"] in existing_urls:
                print(f"    중복 게시글 발견 → 종료")
                stopped = True
                break
            all_posts.append(post)

        if stopped:
            break

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
    return success


def main():
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=HEADLESS)
            context = browser.new_context()
            page = context.new_page()

            print("네이버 로그인 중...")
            login(page)
            print("로그인 완료")

            print("\n크롤링 시작...")
            all_posts = crawl_all_pages(page)
            print(f"\n총 {len(all_posts)}개 게시글 수집 완료")

            browser.close()

        saved = save_to_supabase(all_posts)
        if saved == 0:
            client = create_client(SUPABASE_URL, SUPABASE_KEY)
            total = client.table("cafe_posts").select("id", count="exact").execute().count
            msg = f"새 게시글 없음 (기존 {total}개 유지)"
        else:
            msg = f"새 게시글 {saved}개 저장 완료"
        write_status("done", msg)
        notify("오파독 크롤링 완료 ✅", msg)
    except Exception as e:
        print(f"크롤링 오류: {e}")
        write_status("error", str(e))
        notify("오파독 크롤링 실패 ❌", str(e), priority="high")
        raise


if __name__ == "__main__":
    main()
