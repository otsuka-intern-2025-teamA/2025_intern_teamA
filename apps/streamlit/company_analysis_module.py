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
    key = settings.tavily_api_key
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
        else:
            # デフォルトタイトル（案件一覧ページと同じスタイル）
            st.title("企業分析")
            default_company = ""
    
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
                hits = run_search(company.strip(), count=int(top_k))

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
