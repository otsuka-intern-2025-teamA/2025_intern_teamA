import re
from datetime import datetime
from pathlib import Path

import streamlit as st

# 画像ファイルのパス定義
PROJECT_ROOT = Path(__file__).parent.parent.parent
LOGO_PATH = PROJECT_ROOT / "data" / "images" / "otsuka_logo.jpg"
ICON_PATH = PROJECT_ROOT / "data" / "images" / "otsuka_icon.png"

# 企業分析/スライド作成モジュール
from company_analysis_module import render_company_analysis_page

# API クライアント
from lib.api import APIError, api_available, format_date, get_api_client

# 共通スタイル + HTMLヘルパー
from lib.styles import (
    apply_main_styles,
    apply_projects_list_page_styles,  # ← このページ専用CSS(サイドバー圧縮/ロゴカード等)
    apply_title_styles,  # ← タイトルの基本スタイルを適用
    render_projects_list_title,  # ← タイトル描画
    render_sidebar_logo_card,  # ← サイドバー上部ロゴ
)
from slide_generation_module import render_slide_generation_page

# ---- ページ設定(最初に実行)
st.set_page_config(
    page_title="案件一覧",
    page_icon=str(ICON_PATH),
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={"Get Help": None, "Report a bug": None, "About": None},
)

# ---- 共通スタイル適用(サイドバーを出す)
apply_main_styles(hide_sidebar=False, hide_header=True)
apply_title_styles()
apply_projects_list_page_styles()  # ← このページの余白/ロゴカード/サイドバー圧縮

# ---- セッション初期化
if "selected_project" not in st.session_state:
    st.session_state.selected_project = None
if "projects" not in st.session_state:
    st.session_state.projects = []
if "edit_id" not in st.session_state:
    st.session_state.edit_id = None
if "api_error" not in st.session_state:
    st.session_state.api_error = None
if "current_page" not in st.session_state:
    st.session_state.current_page = "案件一覧"


def _fmt(d):
    if hasattr(d, "strftime"):
        return d.strftime("%Y/%m/%d")
    try:
        return datetime.fromisoformat(str(d)).strftime("%Y/%m/%d")
    except Exception:
        return str(d)


def _to_dt(v) -> datetime:
    """安全に日時へ。失敗したら最小値で返す(古い順などの安定ソート用)"""
    if isinstance(v, datetime):
        return v
    s = str(v) if v is not None else ""
    s = s.replace("Z", "+00:00")
    for fmt in ("%Y-%m-%dT%H:%M:%S%z",
                "%Y-%m-%dT%H:%M:%S.%f%z",
                "%Y-%m-%dT%H:%M:%S",
                "%Y/%m/%d",
                "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt)
        except Exception:
            pass
    try:
        return datetime.fromisoformat(s)
    except Exception:
        return datetime.min


def _switch_page(page_file: str, project_data=None):
    if page_file == "企業分析":
        st.session_state.current_page = "企業分析"
        if project_data:
            st.session_state.selected_project = project_data
        st.session_state.page_changed = True
        st.rerun()
    elif page_file == "スライド作成":
        st.session_state.current_page = "スライド作成"
        if project_data:
            st.session_state.selected_project = project_data
        st.session_state.page_changed = True
        st.rerun()
    else:
        st.error(f"不明なページ: {page_file}")
        st.info("この機能は現在開発中です。")


# ---- ダイアログ
Dialog = getattr(st, "dialog", None) or getattr(st, "experimental_dialog", None)

if Dialog:
    @Dialog("新規案件の作成")
    def open_new_dialog():
        with st.form("new_project_form", clear_on_submit=True):
            title = st.text_input("案件名 *")
            company = st.text_input("企業名 *")
            summary = st.text_area("概要", "")
            submitted = st.form_submit_button("作成")
        if submitted:
            if not title.strip() or not company.strip():
                st.error("案件名と企業名は必須です。")
                st.stop()
            try:
                if api_available():
                    api = get_api_client()
                    new_item_data = {
                        "title": title.strip(),
                        "company_name": company.strip(),
                        "description": summary.strip() or "—",
                    }
                    result = api.create_item(new_item_data)
                    st.success(f"案件「{result['title']}」を作成しました。")
                    st.session_state.api_error = None
                else:
                    st.error("🔌 APIサーバーに接続できません。")
                    return
            except APIError as e:
                st.error(f"❌ 案件作成エラー: {e}")
                return
            except Exception as e:
                st.error(f"⚠️ 予期しないエラー: {e}")
                return
            st.rerun()

    @Dialog("案件の編集 / 削除")
    def open_edit_dialog(pj):
        with st.form("edit_project_form"):
            title = st.text_input("案件名 *", pj.get("title", ""))
            company = st.text_input("企業名 *", pj.get("company", ""))
            summary = st.text_area("概要", pj.get("summary", ""))
            confirm_del = st.checkbox("削除を確認する")
            c1, c2 = st.columns(2)
            with c1:
                saved = st.form_submit_button("保存")
            with c2:
                deleted = st.form_submit_button("削除")

        if saved:
            if not title.strip() or not company.strip():
                st.error("案件名と企業名は必須です。")
                st.stop()
            try:
                if api_available():
                    api = get_api_client()
                    update_data = {
                        "title": title.strip(),
                        "company_name": company.strip(),
                        "description": summary.strip() or "—",
                    }
                    result = api.update_item(pj["id"], update_data)
                    st.success(f"案件「{result['title']}」を更新しました。")
                    st.session_state.api_error = None
                else:
                    st.error("🔌 APIサーバーに接続できません。")
                    return
            except APIError as e:
                st.error(f"❌ 案件更新エラー: {e}")
                return
            except Exception as e:
                st.error(f"⚠️ 予期しないエラー: {e}")
                return
            st.rerun()

        if deleted:
            if not confirm_del:
                st.error("削除にはチェックが必要です。")
                return
            try:
                if api_available():
                    api = get_api_client()
                    api.delete_item(pj["id"])
                    st.success(f"案件「{pj['title']}」を削除しました。")
                    st.session_state.api_error = None
                else:
                    st.error("🔌 APIサーバーに接続できません。")
                    return
            except APIError as e:
                st.error(f"❌ 案件削除エラー: {e}")
                return
            except Exception as e:
                st.error(f"⚠️ 予期しないエラー: {e}")
                return
            st.rerun()
else:
    def open_new_dialog():
        st.warning("このStreamlitではダイアログ未対応です")

    def open_edit_dialog(pj):
        st.warning("このStreamlitではダイアログ未対応です")


# =========================
# 案件一覧ページ本体
# =========================
if st.session_state.current_page == "企業分析":
    render_company_analysis_page()
elif st.session_state.current_page == "スライド作成":
    render_slide_generation_page()
else:
    st.session_state.current_page = "案件一覧"

    # ---------- サイドバー ----------
    with st.sidebar:
        # ロゴ(白背景ラウンドボックス)
        render_sidebar_logo_card(LOGO_PATH)

        # 並び替え
        sort_choice = st.selectbox(
            "並び順",
            [
                "最終更新（新しい順）",
                "最終更新（古い順）",
                "作成日（新しい順）",
                "作成日（古い順）",
                "企業名（A→Z）",
                "企業名（Z→A）",
                "案件名（A→Z）",
                "案件名（Z→A）",
            ],
            index=0,
            key="projects_sort_choice",
            help="カードの並び順を切り替えます",
        )

        # 検索・フィルタ
        keyword = st.text_input(
            "キーワード検索",
            value=st.session_state.get("projects_search_keyword", ""),
            key="projects_search_keyword",
            placeholder="案件名・企業名・概要で検索",
        )
        has_tx_only = st.checkbox(
            "取引がある案件のみ",
            value=st.session_state.get("projects_has_tx_only", False),
            key="projects_has_tx_only",
        )

        # アクション
        st.markdown("### アクション")
        col_a1, col_a2 = st.columns(2)
        with col_a1:
            if st.button("更新", use_container_width=True):
                st.rerun()
        with col_a2:
            if st.button("＋ 新規作成", use_container_width=True):
                open_new_dialog()

    # ---------- タイトル ----------
    render_projects_list_title("案件一覧")

    # ---------- データ取得 ----------
    def fetch_items_from_api():
        """APIから最新の案件データを取得する"""
        try:
            if api_available():
                api = get_api_client()
                api_items = api.get_items()

                items = []
                for item in api_items:
                    created_raw = item.get("created_at")
                    updated_raw = item.get("updated_at")
                    last_order_raw = item.get("last_order_date")
                    formatted_item = {
                        "id": item["id"],
                        "title": item["title"],
                        "company": item["company_name"],
                        "status": "調査中",  # デフォルトステータス
                        "created": format_date(created_raw),
                        "updated": format_date(updated_raw),
                        "summary": item.get("description") or "—",
                        "transaction_count": item.get("transaction_count", 0),
                        "total_amount": item.get("total_amount", 0),
                        "last_order_date": last_order_raw,
                        "user_message_count": item.get("user_message_count", 0),
                        # ソート用の生値
                        "_created_raw": created_raw,
                        "_updated_raw": updated_raw,
                        "_last_order_raw": last_order_raw,
                    }
                    items.append(formatted_item)

                st.session_state.projects = items
                st.session_state.api_error = None
                return items
            else:
                if st.session_state.api_error != "connection":
                    st.error("🔌 バックエンドAPIに接続できません。FastAPIサーバーが起動していることを確認してください。")
                    st.session_state.api_error = "connection"
                return st.session_state.projects
        except APIError as e:
            if st.session_state.api_error != str(e):
                st.error(f"❌ API エラー: {e}")
                st.session_state.api_error = str(e)
            return st.session_state.projects
        except Exception as e:
            if st.session_state.api_error != str(e):
                st.error(f"⚠️ 予期しないエラー: {e}")
                st.session_state.api_error = str(e)
            return st.session_state.projects

    items = fetch_items_from_api()

    # ---------- 検索・フィルタ適用(※ 総取引額下限なし) ----------
    def _match_keyword(p, kw: str) -> bool:
        if not kw:
            return True
        kw = kw.strip().lower()
        hay = " ".join([
            str(p.get("title", "")),
            str(p.get("company", "")),
            str(p.get("summary", "")),
        ]).lower()
        hay = re.sub(r"\s+", " ", hay)
        return kw in hay

    filtered = []
    for p in items:
        if has_tx_only and p.get("transaction_count", 0) <= 0:
            continue
        if not _match_keyword(p, keyword):
            continue
        filtered.append(p)

    # ---------- 並び替え(※ 金額/回数/最終発注日は除外) ----------
    sort_map = {
        "最終更新（新しい順）":  lambda x: (_to_dt(x.get("_updated_raw") or x.get("updated")),),
        "最終更新（古い順）":    lambda x: (_to_dt(x.get("_updated_raw") or x.get("updated")),),
        "作成日（新しい順）":    lambda x: (_to_dt(x.get("_created_raw") or x.get("created")),),
        "作成日（古い順）":      lambda x: (_to_dt(x.get("_created_raw") or x.get("created")),),
        "企業名（A→Z）":        lambda x: (str(x.get("company", "")).lower(),),
        "企業名（Z→A）":        lambda x: (str(x.get("company", "")).lower(),),
        "案件名（A→Z）":        lambda x: (str(x.get("title", "")).lower(),),
        "案件名（Z→A）":        lambda x: (str(x.get("title", "")).lower(),),
    }
    key_fn = sort_map.get(sort_choice, sort_map["最終更新（新しい順）"])
    reverse = sort_choice in {
        "最終更新（新しい順）",
        "作成日（新しい順）",
        "企業名（Z→A）",
        "案件名（Z→A）",
    }
    filtered.sort(key=key_fn, reverse=reverse)

    # ---------- カード描画(1行=2列固定) ----------
    if not filtered:
        st.info("表示できる案件がありません。検索条件やフィルタを見直してください。")
    else:
        cols_per_row = 2  # ← 固定
        rows = (len(filtered) + cols_per_row - 1) // cols_per_row

        for r in range(rows):
            cols = st.columns(cols_per_row)
            for i, col in enumerate(cols):
                idx = r * cols_per_row + i
                if idx >= len(filtered):
                    break
                p = filtered[idx]
                with col:
                    with st.container(border=True):
                        h1, h2 = st.columns([10, 1])
                        with h1:
                            st.markdown(
                                f'<div class="title">{p["title"]}<span class="tag">{p["status"]}</span></div>',
                                unsafe_allow_html=True,
                            )
                        with h2:
                            if st.button("✏️", key=f"edit_{p['id']}", help="編集/削除", use_container_width=True, type="secondary"):
                                open_edit_dialog(p)
                        st.markdown(f'<div class="company">{p["company"]}</div>', unsafe_allow_html=True)

                        meta_info = []
                        meta_info.append(f"・最終更新：{_fmt(p.get('updated'))}")
                        meta_info.append(f"・作成日：{_fmt(p.get('created'))}")
                        meta_info.append(f"・概要：{p.get('summary', '—')}")
                        if p.get("transaction_count", 0) > 0:
                            meta_info.append(f"・取引履歴：{p['transaction_count']}件")
                            if p.get("total_amount", 0) > 0:
                                meta_info.append(f"・総取引額：¥{p['total_amount']:,.0f}")
                            if p.get("last_order_date"):
                                meta_info.append(f"・最終発注：{format_date(p['last_order_date'])}")
                        else:
                            meta_info.append("・取引履歴：未リンク")
                        meta_info.append(f"・チャット回数：{p.get('user_message_count', 0)}回")

                        st.markdown(
                            f'<div class="meta">{"".join([f"{info}<br>" for info in meta_info])}</div>',
                            unsafe_allow_html=True,
                        )
                        b1, b2 = st.columns(2)
                        with b1:
                            if st.button("企業分析", key=f"analysis_{p['id']}", use_container_width=True):
                                st.session_state.selected_project = p
                                _switch_page("企業分析", p)
                        with b2:
                            if st.button("スライド作成", key=f"slides_{p['id']}", use_container_width=True):
                                st.session_state.selected_project = p
                                _switch_page("スライド作成", p)
