import os
import requests
import streamlit as st
import pandas as pd
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(page_title="오파독 과제 게시글 대시보드", layout="wide")

st.markdown("""
<style>
div[data-testid="stVerticalBlockBorderWrapper"] {
    height: calc(100vh - 280px) !important;
    max-height: none !important;
}
div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"]:nth-child(2) {
    position: sticky !important;
    top: 70px !important;
    align-self: flex-start !important;
}
div[data-testid="stButton"] > button {
    background: none !important;
    border: none !important;
    padding: 0 !important;
    color: #4da6ff !important;
    text-decoration: underline !important;
    cursor: pointer !important;
    font-size: 14px !important;
    font-weight: normal !important;
    box-shadow: none !important;
    min-height: unset !important;
    height: auto !important;
}
div[data-testid="stButton"] > button:hover {
    color: #80c0ff !important;
}
button[kind="primary"] {
    background: #1f77b4 !important;
    border: 1px solid #1f77b4 !important;
    color: white !important;
    text-decoration: none !important;
    padding: 4px 16px !important;
    border-radius: 4px !important;
    font-size: 14px !important;
    height: auto !important;
    min-height: unset !important;
}
</style>
""", unsafe_allow_html=True)


@st.cache_resource
def get_client():
    return create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])


@st.cache_data(ttl=300)
def load_posts():
    client = get_client()
    rows = []
    page = 0
    while True:
        res = (
            client.table("cafe_posts")
            .select("title,author,written_at,post_url")
            .range(page * 1000, page * 1000 + 999)
            .execute()
        )
        if not res.data:
            break
        rows.extend(res.data)
        if len(res.data) < 1000:
            break
        page += 1
    return pd.DataFrame(rows)


@st.cache_data(ttl=60)
def load_memos():
    client = get_client()
    res = client.table("author_memos").select("author,memo").execute()
    return {row["author"]: row["memo"] for row in res.data}


def save_memo(author, memo):
    client = get_client()
    client.table("author_memos").upsert(
        {"author": author, "memo": memo},
        on_conflict="author"
    ).execute()
    load_memos.clear()


def render_author_table(df, memos, author_rows, tab_key):
    """author_rows: list of (rank, author, count)"""
    # 헤더
    h1, h2, h3, h4 = st.columns([0.3, 1.2, 0.5, 4])
    h1.markdown("**#**")
    h2.markdown("**작성자**")
    h3.markdown("**게시글 수**")
    h4.markdown("**게시글 목록**")
    st.markdown("<hr style='margin:4px 0;border-color:#555;'>", unsafe_allow_html=True)

    for rank, author, count in author_rows:
        c1, c2, c3, c4 = st.columns([0.3, 1.2, 0.5, 4])
        c1.markdown(f"<div style='padding-top:6px'>{rank}</div>", unsafe_allow_html=True)

        if c2.button(author, key=f"btn_{tab_key}_{author}"):
            st.session_state[f"selected_{tab_key}"] = author

        c3.markdown(f"<div style='padding-top:6px;text-align:center'>{count}</div>", unsafe_allow_html=True)

        author_posts = df[df["author"] == author][["title", "post_url"]]
        links = "　".join(
            f'<a href="{r["post_url"]}" target="_blank" style="font-size:13px;">{r["title"]}</a>'
            for _, r in author_posts.iterrows()
        )
        c4.markdown(f"<div style='padding-top:6px;line-height:2;'>{links}</div>", unsafe_allow_html=True)

        st.markdown("<hr style='margin:2px 0;border-color:#333;'>", unsafe_allow_html=True)


def render_memo_panel(memos, selected, tab_key):
    if not selected:
        st.markdown(
            "<div style='color:#888;margin-top:60px;text-align:center;'>← 작성자 이름을 클릭하면<br>메모를 입력할 수 있어요</div>",
            unsafe_allow_html=True
        )
        return

    st.subheader(f"✏️ {selected}")
    current_memo = memos.get(selected, "")

    edit_key = f"edit_mode_{tab_key}"
    if edit_key not in st.session_state:
        st.session_state[edit_key] = False

    if tab_key == "t2" or st.session_state[edit_key]:
        new_memo = st.text_area(
            "메모", value=current_memo, max_chars=500, height=200,
            key=f"textarea_{tab_key}_{selected}"
        )
        col1, col2 = st.columns([1, 4])
        with col1:
            if st.button("저장", key=f"save_{tab_key}", type="primary"):
                save_memo(selected, new_memo)
                st.session_state[edit_key] = False
                st.success("저장됐습니다.")
                st.rerun()
        if tab_key == "t1":
            with col2:
                if st.button("취소", key=f"cancel_{tab_key}"):
                    st.session_state[edit_key] = False
                    st.rerun()
    else:
        memo_display = current_memo if current_memo else "(메모 없음)"
        st.markdown(
            f"<div style='background:#1e1e1e;padding:12px;border-radius:6px;font-size:14px;line-height:1.8;min-height:80px;'>{memo_display}</div>",
            unsafe_allow_html=True
        )
        if st.button("수정", key=f"edit_btn_{tab_key}", type="primary"):
            st.session_state[edit_key] = True
            st.rerun()


# ─────────────────────────────────────────────────────────────────────────────

col_title, col_btn = st.columns([8, 2])
with col_title:
    st.title("오파독 과제 게시글 대시보드")
with col_btn:
    st.markdown("<div style='margin-top:18px;'>", unsafe_allow_html=True)
    if st.button("🔄 수동 크롤링", type="primary"):
        api_url = os.environ.get("CRAWL_API_URL", "")
        api_token = os.environ.get("CRAWL_API_TOKEN", "")
        try:
            res = requests.post(
                api_url,
                headers={"Authorization": f"Bearer {api_token}"},
                timeout=10,
            )
            if res.ok:
                st.success("크롤링 시작됨! 완료 후 새로고침하세요.")
            else:
                st.error(f"오류: {res.status_code}")
        except Exception as e:
            st.error(str(e))
    st.markdown("</div>", unsafe_allow_html=True)

df = load_posts()
st.caption(f"총 {len(df)}개 게시글 수집됨")

tab1, tab2 = st.tabs(["상위 20명 작성자", "작성자 검색"])

# ── 탭 1 ─────────────────────────────────────────────────────────────────────
with tab1:
    memos = load_memos()

    top20 = (
        df.groupby("author")
        .size()
        .reset_index(name="게시글 수")
        .sort_values("게시글 수", ascending=False)
        .query("`게시글 수` >= 2")
        .reset_index(drop=True)
    )

    st.subheader(f"2개 이상 작성자 ({len(top20)}명)")

    author_rows = [
        (i + 1, row["author"], int(row["게시글 수"]))
        for i, (_, row) in enumerate(top20.iterrows())
    ]

    left, right = st.columns([6, 4])

    with left:
        with st.container(height=2000):
            render_author_table(df, memos, author_rows, "t1")

        st.divider()
        st.download_button(
            label="전체 데이터 CSV로 가져오기",
            data=df.to_csv(index=False).encode("utf-8-sig"),
            file_name="cafe_posts.csv",
            mime="text/csv",
        )

    with right:
        render_memo_panel(memos, st.session_state.get("selected_t1"), "t1")

# ── 탭 2 ─────────────────────────────────────────────────────────────────────
with tab2:
    memos = load_memos()
    search = st.text_input("작성자 이름 입력 (비워두면 전체 표시)")

    all_authors = (
        df.groupby("author")
        .size()
        .reset_index(name="게시글 수")
        .sort_values("게시글 수", ascending=False)
        .reset_index(drop=True)
    )
    if search:
        all_authors = all_authors[all_authors["author"].str.contains(search, na=False)]

    st.caption(f"{len(all_authors)}명 표시 중")

    if all_authors.empty:
        st.warning("검색 결과가 없습니다.")
    else:
        author_rows2 = [
            (i + 1, row["author"], int(row["게시글 수"]))
            for i, (_, row) in enumerate(all_authors.iterrows())
        ]

        left2, right2 = st.columns([6, 4])

        with left2:
            with st.container(height=2000):
                render_author_table(df, memos, author_rows2, "t2")

        with right2:
            render_memo_panel(memos, st.session_state.get("selected_t2"), "t2")
