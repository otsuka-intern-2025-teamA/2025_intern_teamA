import os
import time
from pathlib import Path

import requests

# 履歴の保存/復元
from lib.api import APIError, get_api_client
from lib.company_analysis.data import SearchHit
from lib.company_analysis.llm import (
    company_briefing_with_web_search,
    company_briefing_without_web_search,
    generate_tavily_queries,
)

# 共通スタイル(HTML生成もstyles側に集約)
from lib.styles import (
    apply_chat_scroll_script,
    apply_company_analysis_page_styles,  # ← ページ専用CSS注入
    apply_main_styles,
    apply_title_styles,
    render_company_analysis_title,  # ← タイトルh1をstyles側で描画
    render_sidebar_logo_card,  # ← ロゴカードHTMLをstyles側で描画
)

import streamlit as st

# 画像ファイルのパス定義
PROJECT_ROOT = Path(__file__).parent.parent.parent
LOGO_PATH = PROJECT_ROOT / "data" / "images" / "otsuka_logo.jpg"
ICON_PATH = PROJECT_ROOT / "data" / "images" / "otsuka_icon.png"


@st.cache_data(show_spinner=False)
def tavily_search(query: str, count: int = 6) -> list[SearchHit]:
    """
    Tavily search for web information.
    - TAVILY_API_KEY は st.secrets または 環境変数 から取得
    """
    key = os.getenv("TAVILY_API_KEY", "") or st.secrets.get("TAVILY_API_KEY", "")

    hits: list[SearchHit] = []
    if not key:
        return hits

    r = requests.post(
        "https://api.tavily.com/search",
        headers={"Content-Type": "application/json"},
        json={
            "api_key": key,
            "query": query,
            "max_results": int(count),
            "include_answer": False,
            "search_depth": "advanced",
        },
        timeout=20,
    )
    if r.status_code == 200:
        data = r.json()
        for item in data.get("results", []):
            hits.append(
                SearchHit(
                    title=item.get("title", ""),
                    url=item.get("url", ""),
                    snippet=item.get("content", ""),
                    published=item.get("published_date"),
                )
            )
    return hits


def run_search(query: str, count: int = 8) -> list[SearchHit]:
    """Web検索を実行(tavily)"""
    return tavily_search(query, count=count)


def _pick_one_per_query(
    hits_by_query: list[list[SearchHit]],
    target_k: int,
) -> list[SearchHit]:
    """
    1クエリにつき最終1件（=URL重複は避ける）を選び、合計 target_k 件にそろえる。
    - 各クエリのヒットから順に、まだ使っていないURLを1件選ぶ
    - 選べなかったクエリは「残り候補」を保留し、あとで補完
    - それでも不足する場合は、全候補から未使用URLで埋める
    """
    seen_urls: set[str] = set()
    selected: list[SearchHit] = []
    leftovers: list[SearchHit] = []

    def _url_ok(u: str) -> bool:
        u = (u or "").strip()
        return bool(u)

    # 1周目：各クエリから1件ずつ
    for hits in hits_by_query:
        chosen = None
        for h in hits:
            u = (h.url or "").strip()
            if not _url_ok(u):
                continue
            if u in seen_urls:
                # 重複は候補として温存
                leftovers.append(h)
                continue
            chosen = h
            break

        if chosen:
            selected.append(chosen)
            seen_urls.add((chosen.url or "").strip())
            # 余った同一クエリ内の他候補は後補充用に追加
            for h in hits:
                u = (h.url or "").strip()
                if _url_ok(u) and u not in seen_urls and h is not chosen:
                    leftovers.append(h)
        else:
            # そもそも選べなかった（0件 or 全重複）→全部後補充候補へ
            for h in hits:
                u = (h.url or "").strip()
                if _url_ok(u) and u not in seen_urls:
                    leftovers.append(h)

        if len(selected) >= target_k:
            return selected[:target_k]

    # 2周目：不足分を leftovers から補完
    if len(selected) < target_k:
        for h in leftovers:
            u = (h.url or "").strip()
            if not u or u in seen_urls:
                continue
            selected.append(h)
            seen_urls.add(u)
            if len(selected) >= target_k:
                break

    return selected[:target_k]


def render_company_analysis_page():
    """企業分析ページをレンダリング(常時チャット+サイドバー上ロゴ+タイトル上詰め)"""

    # set_page_config は最上流で1回だけ。複数回呼ばれても例外にするので握りつぶす。
    try:
        st.set_page_config(
            page_title="企業分析",
            page_icon=str(ICON_PATH),
            layout="wide",
            initial_sidebar_state="expanded",
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
    apply_main_styles(hide_sidebar=False, hide_header=True)
    apply_title_styles()
    apply_company_analysis_page_styles()

    # ==== 左サイドバー ====
    with st.sidebar:
        render_sidebar_logo_card(LOGO_PATH)

        company = st.text_input(
            "企業名", value=default_company, key="company_input", placeholder="例）大塚商会、NTTデータ など"
        )

        use_web_search = st.toggle(
            "Web検索を使用", value=True, key="use_web_search_toggle",
            help=("オン：企業名でWeb検索を実行し、検索結果と入力をもとに分析\nオフ：ユーザー入力のみをもとに分析"),
        )
        show_history = st.toggle(
            "過去の取引履歴を表示", value=False, key="show_history_toggle",
            help="チェックを入れると、対象企業の過去取引履歴を表示します。",
        )

        # 「総参照URL件数」=「生成クエリ数」
        top_k = st.selectbox(
            "総参照URL件数",
            options=list(range(1, 11)),
            index=5,
            key="top_k_input",
            help="最終的に参照するURLは 1クエリ=1URL でこの件数になります。",
        )

        st.session_state.setdefault("history_reference_count", 3)
        history_count = st.selectbox(
            "直近のチャット履歴の参照数",
            options=list(range(1, 11)),
            key="history_reference_count",
            help="チャット回答時に過去の履歴を文脈として参照します",
        )

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

    # ==== 本文ヘッダ ====
    render_company_analysis_title(title_text)

    # ==== 本文:常時チャット ====
    if "chat_messages" not in st.session_state:
        st.session_state.chat_messages = []

    api = get_api_client()
    if item_id is not None and st.session_state.get("chat_loaded_item_id") != item_id:
        try:
            msgs = api.get_item_messages(item_id)
            st.session_state.chat_messages = [
                {"role": m.get("role", "assistant"), "content": m.get("content", "")} for m in (msgs or [])
            ]
        except APIError as e:
            st.warning(f"チャット履歴の取得に失敗しました: {e}")
        except Exception as e:
            st.warning(f"チャット履歴の取得に失敗しました: {e}")
        st.session_state.chat_loaded_item_id = item_id

    for m in st.session_state.chat_messages:
        with st.chat_message(m["role"]):
            st.markdown(m["content"])

    if st.session_state.chat_messages:
        apply_chat_scroll_script()

    # 入力欄
    prompt = st.chat_input("この企業について知りたいことを入力…")
    if not prompt:
        return

    # 1) ユーザー発言
    with st.chat_message("user"):
        st.markdown(prompt)

    st.session_state.chat_messages.append({"role": "user", "content": prompt})
    if item_id is not None:
        try:
            api.post_item_message(item_id, "user", prompt)
        except Exception as e:
            st.error(f"サーバ保存に失敗しました（user）: {e}")

    # 2) アシスタント処理
    with st.chat_message("assistant"):
        assistant_text = ""
        final_output_placeholder = st.empty()   # ← 最終出力は枠の外
        status_placeholder = st.empty()         # ← 進捗の枠

        try:
            # 直近履歴
            history_n = st.session_state.get("history_reference_count", 3)
            recent_history = (
                st.session_state.chat_messages[-history_n * 2 :]
                if len(st.session_state.chat_messages) > history_n * 2
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
                    with status_placeholder.status("企業分析（Web検索あり）を開始します…", expanded=True) as status:
                        # ① クエリ作成（= 総参照URL件数）
                        k = int(top_k)
                        status.update(label="🔎 クエリ作成中…", state="running")
                        queries = generate_tavily_queries(search_company, prompt.strip(), max_queries=k)
                        if not queries:
                            # フォールバック
                            base = prompt.strip() or "overview"
                            queries = [f"{search_company} {base} {i+1}" for i in range(k)]
                        # 必要なら切り詰め/水増し
                        if len(queries) > k:
                            queries = queries[:k]
                        elif len(queries) < k:
                            # 簡易に補充してちょうどk件へ
                            base = prompt.strip() or "overview"
                            for i in range(k - len(queries)):
                                queries.append(f"{search_company} {base} extra{i+1}")

                        for q in queries:
                            status.write(f"・{q}")

                        # ② Web検索（各クエリ→最大N件取得して1件だけ選ぶ）
                        #    1クエリ=1URLにするため count は少し多め(例:3)で取得し、その中から未使用URLを選出
                        N_CANDIDATES_PER_QUERY = 3
                        status.update(label="🌐 Web検索中…", state="running")
                        hits_by_query: list[list[SearchHit]] = []
                        prog = st.progress(0)
                        for i, q in enumerate(queries):
                            hits_for_q = run_search(q, count=N_CANDIDATES_PER_QUERY)
                            hits_by_query.append(hits_for_q or [])
                            status.write(f"クエリ{i+1}: {q} … 1件選定")
                            prog.progress((i + 1) / max(1, len(queries)))

                        # 1クエリ=1URL の選定
                        final_hits = _pick_one_per_query(hits_by_query, target_k=k)

                        # ログ表示
                        status.write("—— 採用URL——")
                        if final_hits:
                            for idx, h in enumerate(final_hits, 1):
                                u = (h.url or "").strip()
                                t = (h.title or "").strip() or u
                                status.write(f"{idx}. [{t}]({u})")
                        status.write(f"参照URL: {len(final_hits)} / 指定 {k}")

                        if len(final_hits) == 0:
                            status.update(label="⚠️ 検索結果が見つかりませんでした", state="error")
                            assistant_text = "検索結果が得られませんでした。TAVILY_API_KEY を確認してください。"
                        else:
                            # ③ LLM要約
                            status.update(label="🧠 LLMで要約中…", state="running")
                            report = company_briefing_with_web_search(search_company, final_hits, context)
                            assistant_text = str(report)
                            status.update(label="✅ 完了", state="complete")

                    # 進捗枠を閉じ、最終出力を枠の外へ
                    time.sleep(0.2)
                    status_placeholder.empty()
                    if assistant_text:
                        final_output_placeholder.markdown(assistant_text)

            else:
                # LLMのみ
                target_company = (company or "").strip() or default_company
                if not target_company:
                    st.warning("企業名を入力してください。")
                    assistant_text = "企業名が未入力です。"
                else:
                    with status_placeholder.status("企業分析（LLMのみ）を開始します…", expanded=True) as status:
                        status.update(label="📚 履歴コンテキストを準備中…", state="running")
                        status.write(f"直近履歴を参照: {min(history_n, len(st.session_state.chat_messages)//2)} 往復")

                        status.update(label="🧠 LLMで分析中…", state="running")
                        report = company_briefing_without_web_search(target_company, prompt.strip(), context)
                        assistant_text = str(report)
                        status.update(label="✅ 完了", state="complete")

                    time.sleep(0.2)
                    status_placeholder.empty()
                    if assistant_text:
                        final_output_placeholder.markdown(assistant_text)
            
            if show_history:
                import pandas as pd
                history_path = PROJECT_ROOT / "data" / "csv" / "products" / "history.csv"
                target_company = (company or "").strip() or default_company

                if target_company:
                    df_history = pd.read_csv(history_path)
                    filtered_history = df_history[df_history["business_partners"].str.contains(target_company, na=False, case=False)]
                    if not filtered_history.empty:
                        st.subheader(f"{target_company} の取引履歴")
                        st.table(filtered_history)
                    else:
                        st.info(f"{target_company} の取引履歴は見つかりませんでした。")
                else:
                    st.info("企業名が指定されていません。")

        except Exception as e:
            try:
                status_placeholder.empty()
            finally:
                assistant_text = f"LLM分析中にエラーが発生しました: {e}"
                st.error(assistant_text)

    # 3) 応答の保存
    st.session_state.chat_messages.append({"role": "assistant", "content": assistant_text})
    if item_id is not None:
        try:
            api.post_item_message(item_id, "assistant", assistant_text)
        except Exception as e:
            st.error(f"サーバ保存に失敗しました（assistant）: {e}")
