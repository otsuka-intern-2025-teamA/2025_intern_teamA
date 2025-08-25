"""
企業分析モジュール
app.py と並列に配置して、サイドバーなしで動作
"""
import requests
import streamlit as st
from typing import List
from pathlib import Path
from lib.company_analysis.config import get_settings
from lib.company_analysis.data import SearchHit
from lib.company_analysis.llm import (
    company_briefing_with_web_search,
    company_briefing_without_web_search
)
from lib.company_analysis.ui import render_report
from lib.company_analysis.llm import generate_tavily_queries 

# ★ 追加：APIクライアント（履歴の保存/復元に使用）
from lib.api import get_api_client, APIError  # ← 追加

# 共通スタイルモジュールのインポート
from lib.styles import (
    apply_main_styles, 
    apply_logo_styles,
    apply_scroll_script
)

# 画像ファイルのパス定義
PROJECT_ROOT = Path(__file__).parent.parent.parent
LOGO_PATH = PROJECT_ROOT / "data" / "images" / "otsuka_logo.jpg"


@st.cache_data(show_spinner=False)
def tavily_search(query: str, count: int = 6) -> List[SearchHit]:
    """
    Tavily search for web information. Requires TAVILY_API_KEY in env.
    """
    settings = get_settings()
    key = "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"
    hits: List[SearchHit] = []
    if not key:
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
    """企業分析ページをレンダリング"""
    
    # 共通スタイルを適用（案件一覧ページと同じ）
    apply_main_styles()
    apply_scroll_script()
    
    # タイトルとロゴを横並びで表示（案件一覧ページと同じ比率）
    header_col1, header_col2 = st.columns([3, 0.5])
    
    with header_col1:
        # 動的タイトルを表示（位置を上に調整）
        if st.session_state.get("selected_project"):
            project_data = st.session_state.selected_project
            # 案件名と企業名を含むタイトル（案件一覧ページと同じスタイル）
            st.title(f"{project_data['title']} - {project_data['company']}の分析")
            default_company = project_data.get('company', '')
            item_id = project_data.get('id')
        else:
            # デフォルトタイトル（案件一覧ページと同じスタイル）
            st.title("企業分析")
            default_company = ""
            item_id = None
    
    with header_col2:
        # ロゴを右上に配置（案件一覧ページと同じ高さに調整）
        st.markdown("")  # 少し下にスペース
        try:
            # ロゴ画像を表示（共通スタイルモジュールから適用）
            apply_logo_styles()
            st.image(str(LOGO_PATH), width=160, use_container_width=False)
        except FileNotFoundError:
            st.info(f"ロゴ画像が見つかりません: {LOGO_PATH}")
        except Exception as e:
            st.warning(f"ロゴの読み込みエラー: {e}")
    
    # 戻るボタン
    if st.button("← 案件一覧に戻る"):
        st.session_state.current_page = "案件一覧"
        st.session_state.page_changed = True  # ページ変更フラグを設定
        st.rerun()
    
    st.write("会社名を入力すると、公開Web情報からLLMが日本語でブリーフィングを作成します。")

    # ---- ここから、フォーム/チャットの切替（既定はフォームモード）----
    mode = st.radio("モード", ["フォーム", "チャット"], index=0, horizontal=True)

    # 設定（横並び）
    col1, col2 = st.columns(2)
    with col1:
        top_k = st.number_input("検索結果件数", 1, 10, 6, 1)
    with col2:
        use_web_search = st.checkbox(
            "Web検索を使用",
            value=True,
            help=(
                "チェックすると企業名でWeb検索を実行し、"
                "その結果とユーザー入力をもとに分析します。"
                "チェックしない場合はユーザー入力のみを使用します。"
            )
        )

    company = st.text_input("企業名", value=default_company)

    # =========================
    #  A) フォームモード（既存のまま）
    # =========================
    if mode == "フォーム":
        # ユーザー入力フィールド（web検索を使用しない場合に重要）
        if not use_web_search:
            user_input = st.text_area(
                "分析したい内容や質問を入力してください",
                placeholder="例：この企業の強みは何ですか？市場での競争力はどうですか？",
                help="Web検索を使用しない場合、この入力内容をもとにLLMが分析を行います。"
            )
        else:
            user_input = ""
        
        run = st.button("調べる")

        if run and company.strip():
            if use_web_search:
                # Web検索を使用する場合
                st.info("Web検索中…")
                try:
                    queries = generate_tavily_queries(company.strip(), user_input if not use_web_search else "")
                    # 1クエリあたりの取得件数を計算（上限 top_k に近づける）
                    per_query = max(1, int(top_k) // max(1, len(queries)))
                    hits = tavily_multi_search(queries, per_query=per_query)

                    if not hits:
                        st.error(
                            "検索結果が見つかりませんでした。"
                            "TAVILY_API_KEY を設定してください。"
                        )
                        return

                    st.success(f"検索ヒット: {len(hits)} 件")
                    with st.expander("根拠（検索スニペット）を見る", expanded=False):
                        for h in hits:
                            pub = f"（{h.published}）" if h.published else ""
                            st.markdown(
                                f"- **{h.title}** {pub}\n  \n  {h.snippet}\n  \n  {h.url}"
                            )

                    with st.spinner("LLMで要約中…"):
                        report = company_briefing_with_web_search(company.strip(), hits)
                        
                except Exception as e:
                    st.error(f"Web検索中にエラーが発生しました: {str(e)}")
                    return
            else:
                # Web検索を使用しない場合
                if not user_input.strip():
                    st.error(
                        "Web検索を使用しない場合は、"
                        "分析したい内容や質問を入力してください。"
                    )
                    return
                    
                with st.spinner("LLMで分析中…"):
                    try:
                        report = company_briefing_without_web_search(
                            company.strip(),
                            user_input.strip()
                        )
                    except Exception as e:
                        st.error(f"LLM分析中にエラーが発生しました: {str(e)}")
                        return

            # レポートの表示
            try:
                render_report(report)
            except Exception as e:
                st.error(f"レポート表示中にエラーが発生しました: {str(e)}")
                st.write("エラーが発生しましたが、以下が取得できました:")
                st.json(report.to_dict() if hasattr(report, 'to_dict') else str(report))

    # =========================
    #  B) チャットモード（追加）
    # =========================
    else:
        # --- 履歴（セッション & サーバ連携） ---
        if "chat_messages" not in st.session_state:
            st.session_state.chat_messages = []
        # 案件があればサーバから復元（案件切替時のみ）
        api = get_api_client()
        if item_id is not None and st.session_state.get("chat_loaded_item_id") != item_id:
            try:
                msgs = api.get_item_messages(item_id)
                st.session_state.chat_messages = [
                    {"role": m.get("role", "assistant"), "content": m.get("content", "")}
                    for m in msgs or []
                ]
            except APIError as e:
                st.warning(f"チャット履歴の取得に失敗しました: {e}")
            except Exception as e:
                st.warning(f"チャット履歴の取得に失敗しました: {e}")
            st.session_state.chat_loaded_item_id = item_id

        # --- 履歴表示 ---
        for m in st.session_state.chat_messages:
            with st.chat_message(m["role"]):
                st.markdown(m["content"])

        # --- 送信欄 ---
        prompt = st.chat_input("この企業について知りたいことを入力…")
        if prompt:
            # 1) ユーザー発言（画面 & サーバ保存）
            st.session_state.chat_messages.append({"role": "user", "content": prompt})
            if item_id is not None:
                try:
                    api.post_item_message(item_id, "user", prompt)
                except Exception as e:
                    st.error(f"サーバ保存に失敗しました（user）: {e}")

            # 2) LLM呼び出し（フォームと同じロジックを1ターンで実行）
            with st.chat_message("assistant"):
                with st.spinner("🔎 Web検索→LLMで要約中…"):
                    try:
                        if use_web_search:
                            base_company = (company or "").strip() or default_company
                            queries = generate_tavily_queries(base_company, prompt)
                            per_query = max(1, int(top_k) // max(1, len(queries)))
                            hits = tavily_multi_search(queries, per_query=per_query)
                            if not hits:
                                st.warning("検索結果が見つかりませんでした。TAVILY_API_KEY を設定してください。")
                                assistant_text = "検索結果が得られませんでした。"
                            else:
                                report = company_briefing_with_web_search((company or "").strip() or default_company, hits)
                                # チャット内にレポートを直接描画
                                render_report(report)
                                assistant_text = f"レポートを生成しました（{len(hits)}件の検索に基づく）。"
                        else:
                            if not company.strip():
                                st.warning("企業名を入力してください。")
                                assistant_text = "企業名が未入力です。"
                            else:
                                report = company_briefing_without_web_search(company.strip(), prompt.strip())
                                render_report(report)
                                assistant_text = "レポートを生成しました（Web検索なし）。"
                    except Exception as e:
                        assistant_text = f"LLM分析中にエラーが発生しました: {e}"
                        st.error(assistant_text)

            # 3) アシスタント要約テキストを履歴/サーバに保存
            st.session_state.chat_messages.append({"role": "assistant", "content": assistant_text})
            if item_id is not None:
                try:
                    api.post_item_message(item_id, "assistant", assistant_text)
                except Exception as e:
                    st.error(f"サーバ保存に失敗しました（assistant）: {e}")

        # チャット履歴クリアオプション
        with st.expander("オプション"):
            if st.button("この案件のチャット履歴（画面のみ）をクリア"):
                st.session_state.chat_messages = []
                st.success("画面上の履歴をクリアしました（サーバ側は保持）。")
                st.rerun()  # 画面を即座に更新

def tavily_multi_search(queries: List[str], per_query: int = 3) -> List[SearchHit]:
    """複数クエリを順に検索し、URLで重複排除して統合する"""
    seen_urls = set()
    merged: List[SearchHit] = []
    for q in queries:
        hits = tavily_search(q, count=per_query)
        for h in hits:
            url = (h.url or "").strip()
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)
            merged.append(h)
    return merged
