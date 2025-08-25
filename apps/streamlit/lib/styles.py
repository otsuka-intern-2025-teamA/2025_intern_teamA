"""
共通スタイルモジュール（サイドバー/ヘッダ表示を切り替え可能＋HTML描画ヘルパー）
両ページで使用されるCSS/JSと、共通HTMLスニペット描画を管理
"""

import base64
from pathlib import Path
import streamlit as st


# =========================
# 基本スタイル / スクリプト
# =========================

def get_main_styles(*, hide_sidebar: bool = True, hide_header: bool = True) -> str:
    """
    メインの共通スタイルを取得
    - hide_sidebar=True  : サイドバー非表示
      hide_sidebar=False : サイドバー表示（以前の display:none を打ち消す）
    - hide_header=True   : ヘッダ高さ0（非表示）
      hide_header=False  : ヘッダ表示
    """
    css = [
        "<style>",
        # ---- サイドバー表示/非表示切り替え ----
        "section[data-testid='stSidebar'] { " +
        ("display:none !important;" if hide_sidebar else "display:block !important;") +
        " }",
        "div[data-testid='stSidebarNav'] { " +
        ("display:none !important;" if hide_sidebar else "display:block !important;") +
        " }",
        "[data-testid='collapsedControl'] { " +
        ("display:none !important;" if hide_sidebar else "display:block !important;") +
        " }",

        # ---- ヘッダ領域の制御 ----
        "header[data-testid='stHeader'] { " +
        ("height: 0px;" if hide_header else "height: auto !important;") +
        " }",

        # ---- メインコンテナの調整（共通） ----
        ".block-container { "
        "  padding-top: 2rem !important; "
        "  padding-bottom: 2rem !important; "
        "  max-width: 100% !important; "
        "}",

        # ---- container(border=True) をカード風に ----
        "div[data-testid='stVerticalBlockBorderWrapper'] { "
        "  border: 1px solid #E6E6E6 !important; "
        "  border-radius: 16px !important; "
        "  padding: 16px 16px 12px 16px !important; "
        "  box-shadow: 0 4px 12px rgba(0,0,0,0.06) !important; "
        "  background: #FFFFFF !important; "
        "  margin: 0 !important; "
        "}",

        # ---- カード内のタイポ/タグ ----
        ".title { "
        "  font-weight: 900; "
        "  font-size: 1.2rem; "
        "  margin: 0 0 1px 0; "
        "  line-height: 1.2; "
        "  display: flex; align-items: center; gap: 8px; "
        "}",

        ".tag { "
        "  display: inline-block; "
        "  padding: 2px 8px; "
        "  border-radius: 999px; "
        "  background: #F3F6FF; "
        "  color: #2B59FF; "
        "  font-size: 0.8rem; "
        "  line-height: 1.2; "
        "  white-space: nowrap; "
        "}",

        ".company { "
        "  font-size: 1.05rem; "
        "  margin: 0 0 4px 0; "
        "  font-weight: 600; "
        "}",

        ".meta { "
        "  font-size: 0.95rem; "
        "  line-height: 1.6; "
        "  margin: 0; "
        "}",

        # ---- サイドバー表示時の内側余白（見た目を少し整える） ----
        (
            "section[data-testid='stSidebar'] .block-container { "
            "  padding-top: 1rem !important; "
            "  padding-bottom: 1rem !important; "
            "}" if not hide_sidebar else ""
        ),

        "</style>",
    ]
    return "\n".join(filter(None, css))


def get_logo_styles() -> str:
    """ロゴ画像のスタイルを取得"""
    return """
    <style>
    /* ロゴ画像の角丸を完全に無効化（st.image を使う箇所向け） */
    .stImage img {
        border-radius: 0 !important;
        border: none !important;
    }
    </style>
    """


def get_title_styles() -> str:
    """タイトルのスタイル（基本）"""
    return """
    <style>
    .dynamic-title {
        font-size: 1rem !important;
        line-height: 1.3 !important;
        font-weight: 700 !important;
        color: #262730 !important;
        margin: 0 !important;
        padding: 0 !important;
        word-wrap: break-word !important;
        overflow-wrap: break-word !important;
    }
    .stApp h1 {
        word-wrap: break-word !important;
        overflow-wrap: break-word !important;
        line-height: 1.3 !important;
    }
    </style>
    """


def get_scroll_script() -> str:
    return """
    <script>
    setTimeout(function() {
        window.scrollTo(0, 0);
        document.documentElement.scrollTop = 0;
        document.body.scrollTop = 0;
        window.scrollTo({top: 0, behavior: 'instant'});
    }, 100);
    </script>
    """


def get_chat_scroll_script() -> str:
    return """
    <script>
    function scrollToBottom() { window.scrollTo(0, document.body.scrollHeight); }
    window.addEventListener('load', function() { scrollToBottom(); });
    setTimeout(function() { scrollToBottom(); }, 100);
    setTimeout(function() { scrollToBottom(); }, 500);
    </script>
    """


def apply_main_styles(*, hide_sidebar: bool = True, hide_header: bool = True):
    st.markdown(
        get_main_styles(hide_sidebar=hide_sidebar, hide_header=hide_header),
        unsafe_allow_html=True,
    )


def apply_logo_styles():
    st.markdown(get_logo_styles(), unsafe_allow_html=True)


def apply_title_styles():
    st.markdown(get_title_styles(), unsafe_allow_html=True)


def apply_scroll_script():
    st.markdown(get_scroll_script(), unsafe_allow_html=True)


def apply_chat_scroll_script():
    st.markdown(get_chat_scroll_script(), unsafe_allow_html=True)


def apply_all_styles(*, hide_sidebar: bool = True, hide_header: bool = True):
    apply_main_styles(hide_sidebar=hide_sidebar, hide_header=hide_header)
    apply_logo_styles()
    apply_title_styles()
    apply_scroll_script()


# =========================
# ページ固有スタイル（企業分析）
# =========================

def get_company_analysis_page_styles() -> str:
    return """
    <style>
    /* タイトルをさらに上へ（企業分析ページ） */
    h1.company-analysis-title {
        font-size: 2.4rem !important;
        margin-top: -3rem !important;
        margin-bottom: 0.75rem !important;
    }
    /* 本文側コンテナの上余白 */
    .block-container {
        padding-top: 1.25rem !important;
    }
    /* サイドバー上余白を詰める */
    section[data-testid="stSidebar"] .block-container {
        padding-top: 0.25rem !important;
    }
    /* サイドバー：ロゴの白背景ラウンドボックス */
    .sidebar-logo-card {
        background: #FFFFFF;
        border-radius: 16px;
        padding: 12px 14px;
        border: 1px solid rgba(0,0,0,0.06);
        box-shadow: 0 1px 4px rgba(0,0,0,0.04);
        display: flex;
        align-items: center;
        justify-content: center;
        margin-bottom: 12px;
        margin-top: -15px;
    }
    .sidebar-logo-card img {
        max-width: 100%;
        height: auto;
        display: block;
    }
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
    section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p { margin: 0.15rem 0 !important; }
    section[data-testid="stSidebar"] label,
    section[data-testid="stSidebar"] .st-emotion-cache label { margin-bottom: 0.15rem !important; }
    section[data-testid="stSidebar"] .sidebar-logo-card { margin-bottom: 10px !important; }
    </style>
    """


def apply_company_analysis_page_styles():
    st.markdown(get_company_analysis_page_styles(), unsafe_allow_html=True)


# =========================
# ページ固有スタイル（案件一覧）
# =========================

def get_projects_list_page_styles() -> str:
    """
    案件一覧ページ専用CSS
    - タイトル上詰め（同じ見た目に）
    - サイドバー上端・要素間余白の圧縮
    - サイドバーのロゴ白背景ボックス
    """
    return """
    <style>
    /* タイトル上詰め（案件一覧ページ） */
    h1.projects-list-title {
        font-size: 2.4rem !important;
        margin-top: -3.0rem !important;
        margin-bottom: 0.75rem !important;
    }

    /* サイドバー：内側の上パディングをさらに詰める */
    section[data-testid="stSidebar"] .block-container {
        padding-top: 0.25rem !important;
        padding-bottom: 0.8rem !important;
    }

    /* サイドバー：ロゴの白背景ラウンドボックス（分析ページと共通クラス名） */
    .sidebar-logo-card {
        background: #FFFFFF;
        border-radius: 16px;
        padding: 12px 14px;
        border: 1px solid rgba(0,0,0,0.06);
        box-shadow: 0 1px 4px rgba(0,0,0,0.04);
        display: flex;
        align-items: center;
        justify-content: center;
        margin-bottom: 12px;
        margin-top: -15px;
    }
    .sidebar-logo-card img {
        max-width: 100%;
        height: auto;
        display: block;
    }

    /* サイドバー余白を詰めるセット（案件一覧ページ） */
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
# ★ ページ固有スタイル（スライド生成） ← 追加
# =========================

def get_slide_generation_page_styles() -> str:
    """
    スライド生成ページ専用CSS
    - タイトル上詰め（案件一覧と同程度に合わせる。必要なら値は微調整）
    """
    return """
    <style>
    h1.slide-generation-title {
        font-size: 2.4rem !important;
        margin-top: -7.5rem !important;   /* 必要に応じて -2.5〜-3.5rem で微調整 */
        margin-bottom: 0.75rem !important;
    }
    /* LLM提案ビュー（text_area: disabled）の文字色を黒に */
    div[data-testid="stTextArea"] textarea[disabled]{
    color: #111 !important;
    -webkit-text-fill-color: #111 !important; /* Safari用 */
    opacity: 1 !important;                    /* デフォの薄色化を打消し */
    background-color: #fff !important;        /* 背景は白で固定 */
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
    - 画像はbase64埋め込みで描画（外部参照不要）
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
    """企業分析ページのタイトルを描画（クラス付きh1）"""
    st.markdown(f"<h1 class='company-analysis-title'>{text}</h1>", unsafe_allow_html=True)


def render_projects_list_title(text: str):
    """案件一覧ページのタイトルを描画（クラス付きh1）"""
    st.markdown(f"<h1 class='projects-list-title'>{text}</h1>", unsafe_allow_html=True)


def render_slide_generation_title(text: str):
    """スライド生成ページのタイトルを描画（クラス付きh1）"""
    st.markdown(f"<h1 class='slide-generation-title'>{text}</h1>", unsafe_allow_html=True)
