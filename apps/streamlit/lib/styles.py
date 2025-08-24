"""
共通スタイルモジュール
両ページで使用されるCSSとJavaScriptを管理
"""

import streamlit as st

def get_main_styles():
    """メインの共通スタイルを取得"""
    return """
    <style>
    /* サイドバー/ヘッダを非表示 */
    section[data-testid="stSidebar"] { display:none !important; }
    div[data-testid="stSidebarNav"] { display:none !important; }
    [data-testid="collapsedControl"] { display:none !important; }
    header[data-testid="stHeader"] { height: 0px; }
    
    /* メインコンテナの調整 */
    .block-container { 
        padding-top: 2rem !important; 
        padding-bottom: 2rem !important;
        max-width: 100% !important;
    }
    
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
    .title { 
        font-weight: 900; 
        font-size: 1.2rem; 
        margin: 0 0 1px 0; 
        line-height: 1.2; 
        display: flex; 
        align-items: center; 
        gap: 8px; 
    }
    
    .tag { 
        display: inline-block; 
        padding: 2px 8px; 
        border-radius: 999px; 
        background: #F3F6FF; 
        color: #2B59FF; 
        font-size: 0.8rem; 
        line-height: 1.2; 
        white-space: nowrap; 
    }
    
    .company { 
        font-size: 1.05rem; 
        margin: 0 0 4px 0; 
        font-weight: 600; 
    }
    
    .meta { 
        font-size: 0.95rem; 
        line-height: 1.6; 
        margin: 0; 
    }
    </style>
    """

def get_logo_styles():
    """ロゴ画像のスタイルを取得"""
    return """
    <style>
    /* ロゴ画像の角丸を完全に無効化 */
    .stImage img {
        border-radius: 0 !important;
        border: none !important;
    }
    /* Streamlitのデフォルトスタイルを上書き */
    [data-testid="stImage"] img {
        border-radius: 0 !important;
        border: none !important;
    }
    </style>
    """

def get_title_styles():
    """タイトルのスタイルを取得"""
    return """
    <style>
    /* 動的タイトルのスタイル調整 */
    .dynamic-title {
        font-size: 2rem !important;
        line-height: 1.3 !important;
        font-weight: 700 !important;
        color: #262730 !important;
        margin: 0 !important;
        padding: 0 !important;
        word-wrap: break-word !important;
        overflow-wrap: break-word !important;
    }
    
    /* 長いタイトル用の調整 */
    .stApp h1 {
        word-wrap: break-word !important;
        overflow-wrap: break-word !important;
        line-height: 1.3 !important;
    }
    
    /* 企業分析ページのタイトル位置調整 */
    .company-analysis-title {
        margin-top: -0.5rem !important;
        padding-top: 0 !important;
    }
    </style>
    """

def get_scroll_script():
    """ページトップスクロール用のJavaScriptを取得"""
    return """
    <script>
    // 複数の方法でページトップにスクロール
    setTimeout(function() {
        window.scrollTo(0, 0);
        document.documentElement.scrollTop = 0;
        document.body.scrollTop = 0;
        window.scrollTo({top: 0, behavior: 'instant'});
    }, 100);
    </script>
    """

def apply_main_styles():
    """メインの共通スタイルを適用"""
    st.markdown(get_main_styles(), unsafe_allow_html=True)

def apply_logo_styles():
    """ロゴ画像のスタイルを適用"""
    st.markdown(get_logo_styles(), unsafe_allow_html=True)

def apply_title_styles():
    """タイトルのスタイルを適用"""
    st.markdown(get_title_styles(), unsafe_allow_html=True)

def apply_scroll_script():
    """スクロールスクリプトを適用"""
    st.markdown(get_scroll_script(), unsafe_allow_html=True)

def apply_all_styles():
    """全てのスタイルを適用"""
    apply_main_styles()
    apply_logo_styles()
    apply_title_styles()
    apply_scroll_script()
