import os
import streamlit as st
import pandas as pd
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(page_title="오파독 과제 게시글 대시보드", layout="wide")


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


st.title("오파독 과제 게시글 대시보드")

df = load_posts()
st.caption(f"총 {len(df)}개 게시글 수집됨")

tab1, tab2 = st.tabs(["상위 20명 작성자", "작성자 검색"])

# ── 탭 1: 상위 20명 ──────────────────────────────────────────────────────────
with tab1:
    top20 = (
        df.groupby("author")
        .size()
        .reset_index(name="게시글 수")
        .sort_values("게시글 수", ascending=False)
        .query("`게시글 수` >= 2")
        .reset_index(drop=True)
    )
    top20.index = top20.index + 1

    st.subheader(f"2개 이상 작성자 ({len(top20)}명)")

    # HTML 테이블 (게시글 제목 하이퍼링크 포함)
    rows_html = ""
    for rank, (_, row) in enumerate(top20.iterrows(), start=1):
        author = row["author"]
        count = int(row["게시글 수"])
        author_posts = df[df["author"] == author][["title", "post_url"]]
        links = "<br>".join(
            f'<a href="{r["post_url"]}" target="_blank">{r["title"]}</a>'
            for _, r in author_posts.iterrows()
        )
        rows_html += f"""
        <tr>
            <td style="padding:8px 12px;border-bottom:1px solid #333;text-align:center;">{rank}</td>
            <td style="padding:8px 12px;border-bottom:1px solid #333;">{author}</td>
            <td style="padding:8px 12px;border-bottom:1px solid #333;text-align:center;">{count}</td>
            <td style="padding:8px 12px;border-bottom:1px solid #333;line-height:1.8;">{links}</td>
        </tr>"""

    html_table = f"""
    <table style="width:100%;border-collapse:collapse;font-size:14px;">
        <thead>
            <tr style="border-bottom:2px solid #555;">
                <th style="padding:8px 12px;text-align:center;width:40px;">#</th>
                <th style="padding:8px 12px;text-align:left;">작성자</th>
                <th style="padding:8px 12px;text-align:center;width:80px;">게시글 수</th>
                <th style="padding:8px 12px;text-align:left;">게시글 목록</th>
            </tr>
        </thead>
        <tbody>{rows_html}</tbody>
    </table>
    """
    st.markdown(html_table, unsafe_allow_html=True)

    st.download_button(
        label="전체 데이터 CSV로 가져오기",
        data=df.to_csv(index=False).encode("utf-8-sig"),
        file_name="cafe_posts.csv",
        mime="text/csv",
    )

# ── 탭 2: 작성자 검색 ────────────────────────────────────────────────────────
with tab2:
    search = st.text_input("작성자 이름 입력")
    if search:
        filtered = df[df["author"].str.contains(search, na=False)][
            ["title", "author", "written_at", "post_url"]
        ].reset_index(drop=True)

        if filtered.empty:
            st.warning("검색 결과가 없습니다.")
        else:
            st.write(f"총 {len(filtered)}개 게시글")
            st.dataframe(
                filtered,
                use_container_width=True,
                column_config={
                    "title": st.column_config.TextColumn("제목"),
                    "author": st.column_config.TextColumn("작성자"),
                    "written_at": st.column_config.TextColumn("작성일"),
                    "post_url": st.column_config.LinkColumn("링크"),
                },
            )
