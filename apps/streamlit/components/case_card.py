# 案件カード表示
import streamlit as st
from datetime import date, datetime

def _fmt(d):
    if isinstance(d, (date, datetime)): return d.strftime("%Y/%m/%d")
    try:
        return datetime.fromisoformat(str(d)).strftime("%Y/%m/%d")
    except Exception:
        return str(d)

# p: dict(id,title,company,status,created,updated,summary)
# on_edit / on_analysis / on_slides: callable(p)

def render_case_card(p, on_edit, on_analysis, on_slides):
    with st.container(border=True):
        h1, h2 = st.columns([10, 1])
        with h1:
            st.markdown(f'<div class="title">{p["title"]}<span class="tag">{p["status"]}</span></div>', unsafe_allow_html=True)
        with h2:
            if st.button("✏️", key=f"edit_{p['id']}", help="編集/削除", use_container_width=True):
                on_edit(p)

        st.markdown(f'<div class="company">{p["company"]}</div>', unsafe_allow_html=True)
        st.markdown(
            f'<div class="meta">・最終更新：{_fmt(p.get("updated"))}<br>'
            f'・作成日：{_fmt(p.get("created"))}<br>'
            f'・概要：{p.get("summary", "—")}</div>',
            unsafe_allow_html=True,
        )
        c1, c2 = st.columns(2)
        with c1:
            if st.button("企業分析", key=f"analysis_{p['id']}", use_container_width=True):
                on_analysis(p)
        with c2:
            if st.button("スライド生成", key=f"slides_{p['id']}", use_container_width=True):
                on_slides(p)