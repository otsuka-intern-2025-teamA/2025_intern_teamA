import os
import requests
import streamlit as st
from typing import List
from pathlib import Path

from lib.company_analysis.data import SearchHit
from lib.company_analysis.llm import (
    company_briefing_with_web_search,
    company_briefing_without_web_search,
    generate_tavily_queries 
)

# 履歴の保存/復元
from lib.api import get_api_client, APIError

# 共通スタイル（HTML生成もstyles側に集約）
from lib.styles import (
    apply_main_styles,
    apply_chat_scroll_script,
    apply_title_styles,
    apply_company_analysis_page_styles,   # ← ページ専用CSS注入
    render_sidebar_logo_card,             # ← ロゴカードHTMLをstyles側で描画
    render_company_analysis_title,        # ← タイトルh1をstyles側で描画
)

# 画像ファイルのパス定義
PROJECT_ROOT = Path(__file__).parent.parent.parent
LOGO_PATH = PROJECT_ROOT / "data" / "images" / "otsuka_logo.jpg"
ICON_PATH = PROJECT_ROOT / "data" / "images" / "otsuka_icon.png"


@st.cache_data(show_spinner=False)
def tavily_search(query: str, count: int = 6) -> List[SearchHit]:
    """
    Tavily search for web information.
    - TAVILY_API_KEY は st.secrets または 環境変数 から取得
    """
    # 環境変数を優先し、st.secretsをフォールバックとして使用
    key = "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"

    hits: List[SearchHit] = []
    if not key:
        # APIキーが設定されていない場合は空の結果を返す
        return hits

    r = requests.post(
        "https://api.tavily.com/search",
        headers={"Content-Type": "application/json"},
        json={
            "api_key": key,
            "query": query,
            "max_results": count,
            "include_answer": False,
            "search_depth": "advanced"
        },
        timeout=20
    )
    if r.status_code == 200:
        data = r.json()
        for item in data.get("results", []):
            hits.append(SearchHit(
                title=item.get("title", ""),
                url=item.get("url", ""),
                snippet=item.get("content", ""),
                published=item.get("published_date")
            ))
    return hits


def run_search(query: str, count: int = 8) -> List[SearchHit]:
    """Web検索を実行（tavily）"""
    return tavily_search(query, count=count)


def render_company_analysis_page():
    """企業分析ページをレンダリング（常時チャット＋サイドバー上ロゴ＋タイトル上詰め）"""

    # set_page_config は最上流で1回だけ。複数回呼ばれても例外にするので握りつぶす。
    try:
        st.set_page_config(
            page_title="企業分析",
            page_icon=str(ICON_PATH),  # ← Pathはstrに
            layout="wide",
            initial_sidebar_state="expanded"
        )
    except Exception:
        pass

    # ==== 案件コンテキスト ====
    if st.session_state.get("selected_project"):
        project_data = st.session_state.selected_project
        default_company = project_data.get("company", "")
        item_id = project_data.get("id")
        title_text = f"{project_data['title']} - {project_data['company']}の分析"
    else:
        default_company = ""
        item_id = None
        title_text = "企業分析"

    # ==== スタイル適用 ====
    # サイドバーを表示（hide_sidebar=False）。ヘッダは非表示のまま（hide_header=True）。
    apply_main_styles(hide_sidebar=False, hide_header=True)
    apply_title_styles()
    apply_company_analysis_page_styles()   # ← 本ページ専用のCSS（上詰め & サイドバー圧縮 & ロゴカード）

    # ==== 左サイドバー ====
    with st.sidebar:
        # --- ロゴ（白背景ラウンドボックス） ---
        render_sidebar_logo_card(LOGO_PATH)

        # 企業名
        company = st.text_input(
            "企業名",
            value=default_company,
            key="company_input",
            placeholder="例）大塚商会、NTTデータ など"
        )

        # Web検索の有無
        use_web_search = st.checkbox(
            "Web検索を使用",
            value=True,
            key="use_web_search_checkbox",
            help=(
                "オン：企業名でWeb検索を実行し、検索結果と入力をもとに分析\n"
                "オフ：ユーザー入力のみをもとに分析"
            )
        )

        # 検索結果件数
        top_k = st.number_input(
            "検索結果件数",
            min_value=1,
            max_value=10,
            value=6,
            step=1,
            key="top_k_input"
        )

        # 履歴参照件数
        history_count = st.selectbox(
            "直近の履歴を何件参照する",
            options=[1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
            index=2,  # デフォルト3件
            key="history_reference_count_select",
            help="チャット回答時に過去の履歴を文脈として参照します"
        )
        st.session_state.history_reference_count = history_count

        # 画面内チャット履歴クリア（サーバ側は保持）
        if st.button("画面内チャット履歴をクリア", use_container_width=True):
            st.session_state.chat_messages = []
            st.success("画面上の履歴をクリアしました（サーバ側は保持）。")
            st.rerun()

        st.markdown("<div class='sidebar-bottom'>", unsafe_allow_html=True)
        if st.button("← 案件一覧に戻る", use_container_width=True):
            st.session_state.current_page = "案件一覧"
            st.session_state.page_changed = True
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    # ==== 本文ヘッダ（タイトルのみ） ====
    render_company_analysis_title(title_text)  # ← HTMLはstyles側

    # ==== 本文：常時チャット ====
    # 履歴（セッション & サーバ連携）
    if "chat_messages" not in st.session_state:
        st.session_state.chat_messages = []

    api = get_api_client()
    if (item_id is not None and
            st.session_state.get("chat_loaded_item_id") != item_id):
        try:
            msgs = api.get_item_messages(item_id)
            st.session_state.chat_messages = [
                {"role": m.get("role", "assistant"), "content": m.get("content", "")}
                for m in (msgs or [])
            ]
        except APIError as e:
            st.warning(f"チャット履歴の取得に失敗しました: {e}")
        except Exception as e:
            st.warning(f"チャット履歴の取得に失敗しました: {e}")
        st.session_state.chat_loaded_item_id = item_id

    # 履歴表示
    for m in st.session_state.chat_messages:
        with st.chat_message(m["role"]):
            st.markdown(m["content"])

    # 自動スクロール（最下部へ）
    if st.session_state.chat_messages:
        apply_chat_scroll_script()

    # 入力欄（チャットのみ）
    prompt = st.chat_input("この企業について知りたいことを入力…")
    if prompt:
        # 1) ユーザー発言の即時表示
        with st.chat_message("user"):
            st.markdown(prompt)

        # 2) 履歴へ格納 & サーバ保存
        st.session_state.chat_messages.append({"role": "user", "content": prompt})
        if item_id is not None:
            try:
                api.post_item_message(item_id, "user", prompt)
            except Exception as e:
                st.error(f"サーバ保存に失敗しました（user）: {e}")

        # 3) LLM呼び出し
        with st.chat_message("assistant"):
            try:
                # 直近の履歴（ユーザー/アシスタント往復×N件）
                history_n = st.session_state.get("history_reference_count", 3)
                recent_history = (
                    st.session_state.chat_messages[-history_n*2:]
                    if len(st.session_state.chat_messages) > history_n*2
                    else st.session_state.chat_messages
                )
                context = "過去のチャット履歴:\n"
                for msg in recent_history:
                    role = "ユーザー" if msg["role"] == "user" else "アシスタント"
                    context += f"{role}: {msg['content']}\n\n"

                if use_web_search:
                    search_company = (company or "").strip() or default_company
                    if not search_company:
                        st.warning("Web検索を使用する場合は、企業名を入力してください。")
                        assistant_text = "企業名が未入力です。"
                    else:
                        with st.spinner("Web検索→LLMで要約中…"):
                            # ❶ GPTで検索クエリを生成
                            queries = generate_tavily_queries(search_company, prompt.strip(), max_queries=5)
                            all_hits = []
                            for q in queries:
                                hits_for_q = run_search(q, count=int(top_k))
                                if hits_for_q:
                                    all_hits.extend(hits_for_q)

                            # ❷ 結果がゼロの場合
                            if not all_hits:
                                st.warning(
                                    "検索結果が見つかりませんでした。"
                                    "TAVILY_API_KEY を設定してください。"
                                )
                                assistant_text = "検索結果が得られませんでした。"
                            else:
                                # ❸ 集めた結果を使って要約
                                report = company_briefing_with_web_search(search_company, all_hits, context)
                                st.markdown(str(report))
                                assistant_text = str(report)

                else:
                    # Web検索なしで、ユーザー入力＋文脈のみ
                    with st.spinner("LLMで分析中…"):
                        target_company = (company or "").strip() or default_company
                        if not target_company:
                            st.warning("企業名を入力してください。")
                            assistant_text = "企業名が未入力です。"
                        else:
                            report = company_briefing_without_web_search(
                                target_company,
                                prompt.strip(),
                                context
                            )
                            st.markdown(str(report))
                            assistant_text = str(report)
            except Exception as e:
                assistant_text = f"LLM分析中にエラーが発生しました: {e}"
                st.error(assistant_text)

        # 4) アシスタント応答を履歴 & サーバ保存
        st.session_state.chat_messages.append(
            {"role": "assistant", "content": assistant_text}
        )
        if item_id is not None:
            try:
                api.post_item_message(item_id, "assistant", assistant_text)
            except Exception as e:
                st.error(f"サーバ保存に失敗しました（assistant）: {e}")
