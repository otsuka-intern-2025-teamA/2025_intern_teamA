"""
共通スタイルモジュール(安全なサイドバー出し入れ/ヘッダ最小化/カード装飾)
- サイドバー表示は Streamlit に任せ、CSS で display を強制しない
- ヘッダは最小高さで残す(トグルを隠さない)
- トグルを前面固定して常に再表示できるようにする
"""

import base64
from pathlib import Path

import streamlit as st

# =========================
# 基本スタイル / スクリプト
# =========================


def get_main_styles(*, hide_sidebar: bool = False, hide_header: bool = True) -> str:
    """
    メインの共通スタイルを取得

    互換性のため引数は残すが、以下の方針に変更:
    - サイドバーの表示/非表示は CSS で強制しない(toggle を殺さないため)
    - hide_header=True のときもヘッダは「最小高さで残す」
    """
    css = [
        "<style>",
        # ---- サイドバー/トグル:display は一切いじらない ----
        #   * Streamlit の initial_sidebar_state / ユーザー操作に任せる
        #   * 代わりにトグルを常に前面・左上に置いて見失わないようにする
        "[data-testid='collapsedControl'] {"
        "  position: fixed !important;"
        "  top: 8px !important; left: 8px !important;"
        "  z-index: 10000 !important;"
        "  opacity: 1 !important; pointer-events: auto !important;"
        "}",
        # サイドバー展開時、サイドバー内のトグル位置(保険的に)
        "section[data-testid='stSidebar'] [data-testid='collapsedControl'] {"
        "  position: sticky !important; top: 8px !important; left: 8px !important;"
        "}",
        # ---- ヘッダ領域 ----
        #  height:0 をやめて、最小高さ + 透明背景に(トグルが隠れない)
        "header[data-testid='stHeader'] {"
        + (
            "  min-height: 36px !important; height: 36px !important; "
            "  background: transparent !important; box-shadow: none !important;"
            if hide_header
            else "  min-height: 48px !important; height: auto !important; "
        )
        + "}",
        # ---- 本文コンテナの余白(サイドバーとは独立に調整) ----
        "div[data-testid='stAppViewContainer'] .block-container {"
        "  padding-top: 0.75rem !important;"
        "  padding-bottom: 1.5rem !important;"
        "  max-width: 100% !important;"
        "}",
        # ---- container(border=True) をカード風に(.card 直下だけ)----
        ".card > div[data-testid='stVerticalBlockBorderWrapper'] {"
        "  border: 1px solid #E6E6E6 !important;"
        "  border-radius: 16px !important;"
        "  padding: 16px 16px 12px 16px !important;"
        "  box-shadow: 0 4px 12px rgba(0,0,0,0.06) !important;"
        "  background: #FFFFFF !important;"
        "  margin: 0 !important;"
        "  box-sizing: border-box !important;"
        "  max-width: 100% !important;"
        "  min-width: 0 !important;"
        "  overflow: hidden !important;"
        "}",
        # ---- 古いDOMへのフォールバック(.card 直下だけ)----
        ".card > div[data-testid='stVerticalBlock'] {"
        "  border: 1px solid #E6E6E6 !important;"
        "  border-radius: 16px !important;"
        "  padding: 16px 16px 12px 16px !important;"
        "  box-shadow: 0 4px 12px rgba(0,0,0,0.06) !important;"
        "  background: #FFFFFF !important;"
        "  box-sizing: border-box !important;"
        "  max-width: 100% !important;"
        "  min-width: 0 !important;"
        "  overflow: hidden !important;"
        "}",
        # ---- 長文で崩さない(カード内だけに限定)----
        ".card * {  word-break: break-word !important;  overflow-wrap: anywhere !important;}",
        # ---- カード内のタイポ/タグ ----
        ".title {"
        "  font-weight: 900; font-size: 1.2rem; margin: 0 0 1px 0;"
        "  line-height: 1.2; display: flex; align-items: center; gap: 8px;"
        "}",
        ".tag {"
        "  display: inline-block; padding: 2px 8px; border-radius: 999px;"
        "  background: #F3F6FF; color: #2B59FF; font-size: 0.8rem; line-height: 1.2;"
        "  white-space: nowrap;"
        "}",
        ".company { font-size: 1.05rem; margin: 0 0 4px 0; font-weight: 600; }",
        ".meta { font-size: 0.95rem; line-height: 1.6; margin: 0; }",
        # ---- サイドバー内の余白最適化(display は変更しない) ----
        "section[data-testid='stSidebar'] .block-container {"
        "  padding-top: 0.25rem !important; padding-bottom: 0.8rem !important;"
        "}",
        "</style>",
    ]
    return "\n".join(css)


def get_title_styles() -> str:
    """タイトルの基本スタイル(過度な負マージンを使わない)"""
    return """
    <style>
    .dynamic-title {
        font-size: 1rem !important;
        line-height: 1.3 !important;
        font-weight: 700 !important;
        color: #262730 !important;
        margin: 0 !important; padding: 0 !important;
        word-wrap: break-word !important; overflow-wrap: break-word !important;
    }
    .stApp h1 { word-wrap: break-word !important; overflow-wrap: break-word !important; line-height: 1.3 !important; }
    </style>
    """


def get_chat_scroll_script() -> str:
    return """
    <script>
    function scrollToBottom(){ window.scrollTo(0, document.body.scrollHeight); }
    window.addEventListener('load', function(){ scrollToBottom(); });
    setTimeout(function(){ scrollToBottom(); }, 100);
    </script>
    """


def apply_main_styles(*, hide_sidebar: bool = False, hide_header: bool = True):
    # 引数は互換のため残しているが、上記方針で安全に適用
    st.markdown(get_main_styles(hide_sidebar=hide_sidebar, hide_header=hide_header), unsafe_allow_html=True)


def apply_title_styles():
    st.markdown(get_title_styles(), unsafe_allow_html=True)


def apply_chat_scroll_script():
    st.markdown(get_chat_scroll_script(), unsafe_allow_html=True)


# =========================
# ページ固有スタイル(企業分析)
# =========================


def get_company_analysis_page_styles() -> str:
    return """
    <style>
    /* タイトル:負マージンを撤廃 */
    h1.company-analysis-title {
        font-size: 2.4rem !important;
        margin-top: 0 !important;
        margin-bottom: 0.75rem !important;
    }
    /* 本文側コンテナの上余白(控えめに) */
    div[data-testid="stAppViewContainer"] .block-container { padding-top: 0.75rem !important; }

    /* サイドバー:ロゴの白背景ラウンドボックス */
    .sidebar-logo-card {
        background: #FFFFFF; border-radius: 16px; padding: 12px 14px;
        border: 1px solid rgba(0,0,0,0.06); box-shadow: 0 1px 4px rgba(0,0,0,0.04);
        display: flex; align-items: center; justify-content: center;
        margin-bottom: 12px; margin-top: -8px;
    }
    .sidebar-logo-card img { max-width: 100%; height: auto; display: block; }

    /* サイドバー余白を詰めるセット */
    section[data-testid="stSidebar"] .block-container > div { margin-bottom: 0rem !important; }
    section[data-testid="stSidebar"] h3 { margin: 0rem 0 0rem !important; }
    section[data-testid="stSidebar"] [data-testid="stDivider"] { margin: 0rem 0 !important; }
    section[data-testid="stSidebar"] .stButton,
    section[data-testid="stSidebar"] .stTextInput,
    section[data-testid="stSidebar"] .stCheckbox,
    section[data-testid="stSidebar"] .stNumberInput,
    section[data-testid="stSidebar"] .stSelectbox,
    section[data-testid="stSidebar"] .stRadio { margin-bottom: 0rem !important; }
    section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p { margin: 0.15rem 0 !識; }
    section[data-testid="stSidebar"] label,
    section[data-testid="stSidebar"] .st-emotion-cache label { margin-bottom: 0.15rem !important; }
    section[data-testid="stSidebar"] .sidebar-logo-card { margin-bottom: 10px !important; }
    </style>
    """


def apply_company_analysis_page_styles():
    st.markdown(get_company_analysis_page_styles(), unsafe_allow_html=True)


# =========================
# ページ固有スタイル(案件一覧)
# =========================


def get_projects_list_page_styles() -> str:
    """
    案件一覧ページ専用CSS
    - タイトル上詰め(負マージンは使わない)
    - サイドバーの上端/要素間余白の圧縮
    """
    return """
    <style>
    h1.projects-list-title {
        font-size: 2.4rem !important;
        margin-top: 0 !important;
        margin-bottom: 0.75rem !important;
    }

    section[data-testid="stSidebar"] .block-container {
        padding-top: 0.25rem !important; padding-bottom: 0.8rem !important;
    }

    .sidebar-logo-card {
        background: #FFFFFF; border-radius: 16px; padding: 12px 14px;
        border: 1px solid rgba(0,0,0,0.06); box-shadow: 0 1px 4px rgba(0,0,0,0.04);
        display: flex; align-items: center; justify-content: center;
        margin-bottom: 12px; margin-top: -8px;
    }
    .sidebar-logo-card img { max-width: 100%; height: auto; display: block; }

    /* サイドバー余白を詰めるセット(案件一覧ページ) */
    section[data-testid="stSidebar"] .block-container > div { margin-bottom: 0.4rem !important; }
    section[data-testid="stSidebar"] h3 { margin: 0.25rem 0 0.2rem !important; }
    section[data-testid="stSidebar"] [data-testid="stDivider"] { margin: 0.4rem 0 !important; }
    section[data-testid="stSidebar"] .stButton,
    section[data-testid="stSidebar"] .stTextInput,
    section[data-testid="stSidebar"] .stCheckbox,
    section[data-testid="stSidebar"] .stNumberInput,
    section[data-testid="stSidebar"] .stSelectbox,
    section[data-testid="stSidebar"] .stRadio { margin-bottom: 0.4rem !important; }
    section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p { margin: 0.2rem 0 !important; }
    section[data-testid="stSidebar"] label,
    section[data-testid="stSidebar"] .st-emotion-cache label { margin-bottom: 0.2rem !important; }
    section[data-testid="stSidebar"] .sidebar-logo-card { margin-bottom: 10px !important; }
    </style>
    """


def apply_projects_list_page_styles():
    st.markdown(get_projects_list_page_styles(), unsafe_allow_html=True)


# =========================
# ページ固有スタイル(スライド生成)
# =========================


def get_slide_generation_page_styles() -> str:
    """スライド生成ページ専用CSS(負マージン廃止)"""
    return """
    <style>
    h1.slide-generation-title {
        font-size: 2.4rem !important;
        margin-top: 0 !important;
        margin-bottom: 0.75rem !important;
    }
    /* LLM提案ビュー(text_area: disabled)の文字色を黒に */
    div[data-testid="stTextArea"] textarea[disabled]{
      color:#111 !important; -webkit-text-fill-color:#111 !important;
      opacity:1 !important; background-color:#fff !important;
    }
    </style>
    """


def apply_slide_generation_page_styles():
    st.markdown(get_slide_generation_page_styles(), unsafe_allow_html=True)


# =========================
# HTML描画ヘルパー
# =========================


def render_sidebar_logo_card(image_path: Path | str):
    """
    サイドバー上部に、白背景の角丸ボックス内にロゴを描画
    - 画像は base64 埋め込みで描画(外部参照不要)
    """
    try:
        p = Path(image_path)
        with p.open("rb") as f:
            b64 = base64.b64encode(f.read()).decode("utf-8")
        mime = "image/png" if p.suffix.lower() == ".png" else "image/jpeg"
        st.markdown(
            f"""
            <div class="sidebar-logo-card">
                <img src="data:{mime};base64,{b64}" alt="logo" />
            </div>
            """,
            unsafe_allow_html=True,
        )
    except FileNotFoundError:
        st.info(f"ロゴ画像が見つかりません: {image_path}")
    except Exception as e:
        st.warning(f"ロゴの読み込みエラー: {e}")


def render_company_analysis_title(text: str):
    st.markdown(f"<h1 class='company-analysis-title'>{text}</h1>", unsafe_allow_html=True)


def render_projects_list_title(text: str):
    st.markdown(f"<h1 class='projects-list-title'>{text}</h1>", unsafe_allow_html=True)


def render_slide_generation_title(text: str):
    st.markdown(f"<h1 class='slide-generation-title'>{text}</h1>", unsafe_allow_html=True)
