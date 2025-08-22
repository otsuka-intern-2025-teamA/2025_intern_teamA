import streamlit as st
from datetime import date, datetime
import re

import streamlit as st
from datetime import date, datetime
import re


# ---- ページ設定 & CSS（サイドバー非表示 + カード見た目）
st.set_page_config(page_title="案件一覧", page_icon="🗂️", layout="wide", initial_sidebar_state="collapsed",
menu_items={"Get Help": None, "Report a bug": None, "About": None})


st.markdown(
"""
<style>
/* サイドバー/ヘッダを非表示 */
section[data-testid="stSidebar"] { display:none !important; }
div[data-testid="stSidebarNav"] { display:none !important; }
[data-testid="collapsedControl"] { display:none !important; }
header[data-testid="stHeader"] { height: 0px; }
.block-container { padding-top: 1rem; }


/* container(border=True) をカード風に */
div[data-testid="stVerticalBlockBorderWrapper"] {
border: 1px solid #E6E6E6 !important;
border-radius: 16px !important;
padding: 16px 16px 12px 16px !important;
box-shadow: 0 4px 12px rgba(0,0,0,0.06) !important;
background: #FFFFFF !important;
margin: 0 !important;
}
/* カード内のタイポ/タグ */
.title { font-weight: 900; font-size: 1.2rem; margin: 0 0 2px 0; line-height: 1.2; display:flex; align-items:center; gap:8px; }
.tag { display:inline-block; padding: 2px 8px; border-radius: 999px; background:#F3F6FF; color:#2B59FF; font-size:0.8rem; line-height:1.2; white-space:nowrap; }
.company { font-size: 1.05rem; margin: 0 0 6px 0; font-weight: 600; }
.meta { font-size: 0.95rem; line-height: 1.6; margin: 0; }
</style>
""",
unsafe_allow_html=True,
)

# ---- レイアウト（サイドバー非表示）
try:
    from apps.streamlit.components.layout import apply_base_ui
    apply_base_ui(hide_sidebar=True)
except Exception:
    st.set_page_config(page_title="案件一覧", page_icon="🗂️", layout="wide", initial_sidebar_state="collapsed")
    st.markdown(
        """
        <style>
        section[data-testid="stSidebar"] {display:none !important;}
        div[data-testid="stSidebarNav"] {display:none !important;}
        [data-testid="collapsedControl"] {display:none !important;}
        header[data-testid="stHeader"] { height: 0px; }
        .block-container { padding-top: 1rem; }
        </style>
        """,
        unsafe_allow_html=True,
    )

# ---- セッション初期化（※インデント必須）
if "selected_project" not in st.session_state:
    st.session_state.selected_project = None
if "projects" not in st.session_state:
    st.session_state.projects = [
        {"id": "A001", "title": "案件A", "company": "株式会社〇〇", "status": "調査中", "created": date(2025,8,1),  "updated": date(2025,8,20), "summary": "新規取引候補の企業調査。"},
        {"id": "B002", "title": "案件B", "company": "株式会社△△", "status": "未着手", "created": date(2025,7,20), "updated": date(2025,8,10), "summary": "RFPに向けて情報収集。"},
        {"id": "C003", "title": "案件C", "company": "株式会社◇◇", "status": "進行中", "created": date(2025,7,25), "updated": date(2025,8,10), "summary": "既存顧客への提案強化。"},
        {"id": "D004", "title": "案件D", "company": "株式会社□□", "status": "調査中", "created": date(2025,7,15), "updated": date(2025,8,5),  "summary": "競合比較のための企業分析。"},
    ]
if "edit_id" not in st.session_state:
    st.session_state.edit_id = None

STATUS_OPTIONS = ["未着手", "調査中", "進行中"]

# ---- ユーティリティ

def _next_project_id(projects):
    nums = []
    for p in projects:
        m = re.findall(r"\d+", p.get("id", ""))
        if m:
            nums.append(int(m[-1]))
    n = (max(nums) + 1) if nums else 1
    return f"N{n:03d}", n


def _fmt(d):
    if hasattr(d, "strftime"):
        return d.strftime("%Y/%m/%d")
    try:
        return datetime.fromisoformat(str(d)).strftime("%Y/%m/%d")
    except Exception:
        return str(d)


def _switch_page(page_file: str):
    fn = getattr(st, "switch_page", None)
    if fn:
        fn(page_file)
    else:
        st.warning("Streamlit が古いため自動遷移できません（1.30+ を推奨）。")

# ---- ダイアログ
Dialog = getattr(st, "dialog", None) or getattr(st, "experimental_dialog", None)

if Dialog:
    @Dialog("新規案件の作成")
    def open_new_dialog():
        with st.form("new_project_form", clear_on_submit=True):
            title = st.text_input("案件名 *")
            company = st.text_input("企業名 *")
            status = st.selectbox("ステータス", STATUS_OPTIONS, index=0)
            summary = st.text_area("概要", "")
            submitted = st.form_submit_button("作成")
        if submitted:
            if not title.strip() or not company.strip():
                st.error("案件名と企業名は必須です。")
                st.stop()
            new_id, n = _next_project_id(st.session_state.projects)
            today = date.today()
            st.session_state.projects.append({
                "id": new_id,
                "title": title.strip(),
                "company": company.strip(),
                "status": status,
                "created": today,
                "updated": today,
                "summary": summary.strip() or "—",
            })
            st.rerun()

    @Dialog("案件の編集 / 削除")
    def open_edit_dialog(pj):
        with st.form("edit_project_form"):
            title = st.text_input("案件名 *", pj.get("title", ""))
            company = st.text_input("企業名 *", pj.get("company", ""))
            status = st.selectbox(
                "ステータス",
                STATUS_OPTIONS,
                index=(STATUS_OPTIONS.index(pj.get("status", "未着手")) if pj.get("status") in STATUS_OPTIONS else 0),
            )
            summary = st.text_area("概要", pj.get("summary", ""))
            confirm_del = st.checkbox("削除を確認する")
            c1, c2 = st.columns(2)
            with c1:
                saved = st.form_submit_button("保存")
            with c2:
                deleted = st.form_submit_button("削除")
        if saved:
            pj.update({
                "title": title.strip(),
                "company": company.strip(),
                "status": status,
                "summary": summary.strip() or "—",
                "updated": date.today(),
            })
            st.success("更新しました。")
            st.rerun()
        if deleted:
            if confirm_del:
                st.session_state.projects = [x for x in st.session_state.projects if x["id"] != pj["id"]]
                st.success("削除しました。")
                st.rerun()
            else:
                st.error("削除にはチェックが必要です。")
else:
    def open_new_dialog():
        st.warning("このStreamlitではダイアログ未対応です")
    def open_edit_dialog(pj):
        st.warning("このStreamlitではダイアログ未対応です")

# ---- 一覧UI
st.title("案件一覧")

c1, c2, c3, c4, c5 = st.columns([2, 2, 2, 3, 1.6])
with c1:
    q = st.text_input("検索（案件名・企業名）", "")
with c2:
    status_filter = st.selectbox("ステータス", ["すべて"] + STATUS_OPTIONS)
with c3:
    sort_key = st.selectbox("並べ替え基準", ["最終更新日", "企業名", "案件名", "作成日"])
with c4:
    order = st.radio("順序", ["降順", "昇順"], horizontal=True)
with c5:
    if st.button("＋ 新規作成", use_container_width=True):
        open_new_dialog()

# フィルタ

def _match(p):
    ok_q = (q.strip() == "") or (q in p.get("title", "")) or (q in p.get("company", "")) or (q in p.get("summary", ""))
    ok_s = (status_filter == "すべて") or (p.get("status") == status_filter)
    return ok_q and ok_s

items = [p for p in st.session_state.projects if _match(p)]

# ソート
key_map = {"最終更新日": "updated", "企業名": "company", "案件名": "title", "作成日": "created"}
rev = (order == "降順")
items.sort(key=lambda x: x.get(key_map[sort_key]), reverse=rev)

# カード描画
cols_per_row = 3 if len(items) >= 3 else 2
rows = (len(items) + cols_per_row - 1) // cols_per_row

for r in range(rows):
    cols = st.columns(cols_per_row)
    for i, col in enumerate(cols):
        idx = r * cols_per_row + i
        if idx >= len(items):
            break
        p = items[idx]
        with col:
            with st.container(border=True):
                h1, h2 = st.columns([10, 1])
                with h1:
                    st.markdown(
                        f'<div class="title">{p["title"]}<span class="tag">{p["status"]}</span></div>',
                        unsafe_allow_html=True,
                    )
                with h2:
                    if st.button("✏️", key=f"edit_{p['id']}", help="編集/削除", use_container_width=True):
                        open_edit_dialog(p)
                st.markdown(f'<div class="company">{p["company"]}</div>', unsafe_allow_html=True)
                st.markdown(
                    f'<div class="meta">・最終更新：{_fmt(p.get("updated"))}<br>'
                    f'・作成日：{_fmt(p.get("created"))}<br>'
                    f'・概要：{p.get("summary", "—")}</div>',
                    unsafe_allow_html=True,
                )
                b1, b2 = st.columns(2)
                with b1:
                    if st.button("企業分析", key=f"analysis_{p['id']}", use_container_width=True):
                        st.session_state.selected_project = p
                        _switch_page("pages/2_企業を知る.py")
                with b2:
                    if st.button("スライド作成", key=f"slides_{p['id']}", use_container_width=True):
                        st.session_state.selected_project = p
                        _switch_page("pages/3_提案を作る.py")
