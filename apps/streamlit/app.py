import streamlit as st
from pathlib import Path

# 画像ファイルのパス定義
PROJECT_ROOT = Path(__file__).parent.parent.parent
LOGO_PATH = PROJECT_ROOT / "data" / "images" / "otsuka_logo.jpg"
ICON_PATH = PROJECT_ROOT / "data" / "images" / "otsuka_icon.png"


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
.title { font-weight: 900; font-size: 1.2rem; margin: 0 0 1px 0; line-height: 1.2; display:flex; align-items:center; gap:8px; }
.tag { display:inline-block; padding: 2px 8px; border-radius: 999px; background:#F3F6FF; color:#2B59FF; font-size:0.8rem; line-height:1.2; white-space:nowrap; }
.company { font-size: 1.05rem; margin: 0 0 4px 0; font-weight: 600; }
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
    st.set_page_config(
        page_title="案件一覧",
        page_icon=str(ICON_PATH),
        layout="wide",
        initial_sidebar_state="collapsed",
        menu_items={"Get Help": None, "Report a bug": None, "About": None}
    )
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

# API クライアントのインポート
from lib.api import get_api_client, api_available, format_date, APIError

# ---- セッション初期化（※インデント必須）
if "selected_project" not in st.session_state:
    st.session_state.selected_project = None
if "projects" not in st.session_state:
    st.session_state.projects = []
if "edit_id" not in st.session_state:
    st.session_state.edit_id = None
if "api_error" not in st.session_state:
    st.session_state.api_error = None


def _fmt(d):
    if hasattr(d, "strftime"):
        return d.strftime("%Y/%m/%d")
    try:
        return datetime.fromisoformat(str(d)).strftime("%Y/%m/%d")
    except Exception:
        return str(d)


def _switch_page(page_file: str):
    # ページが未実装であることを通知
    st.error(f"ページ '{page_file}' はまだ実装されていません。")
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
            
            # API経由で新規案件を作成
            try:
                if api_available():
                    api = get_api_client()
                    new_item_data = {
                        "title": title.strip(),
                        "company_name": company.strip(),
                        "description": summary.strip() or "—"
                    }
                    result = api.create_item(new_item_data)
                    st.success(f"案件「{result['title']}」を作成しました。")
                    st.session_state.api_error = None  # エラー状態をクリア
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
                
            # API経由で案件を更新
            try:
                if api_available():
                    api = get_api_client()
                    update_data = {
                        "title": title.strip(),
                        "company_name": company.strip(),
                        "description": summary.strip() or "—"
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
                
            # API経由で案件を削除
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

# タイトル（左上）とロゴ（右下寄り）を配置
header_col1, header_col2 = st.columns([3, 0.5])

with header_col1:
    st.title("案件一覧")


with header_col2:
    # ロゴを右下寄りに配置
    st.markdown("")  # 少し下にスペース
    st.markdown("")  # さらに下にスペース
    try:
        # 定義済みのロゴパスを使用
        st.image(str(LOGO_PATH), width=120)  # サイズを少し小さく
    except FileNotFoundError:
        st.info(f"ロゴ画像が見つかりません: {LOGO_PATH}")
    except Exception as e:
        st.warning(f"ロゴの読み込みエラー: {e}")

# 新規作成ボタンをより右に配置
st.markdown("")  # 少しスペースを追加
col1, col2 = st.columns([7, 1])
with col2:
    if st.button("＋ 新規作成"):
        open_new_dialog()

# データ取得関数を定義
def fetch_items_from_api():
    """APIから最新の案件データを取得する"""
    try:
        if api_available():
            api = get_api_client()
            api_items = api.get_items()
            
            # APIデータをStreamlit形式に変換
            items = []
            for item in api_items:
                formatted_item = {
                    "id": item["id"],
                    "title": item["title"],
                    "company": item["company_name"],
                    "status": "調査中",  # デフォルトステータス
                    "created": format_date(item["created_at"]),
                    "updated": format_date(item["updated_at"]),
                    "summary": item["description"] or "—",
                    "transaction_count": item.get("transaction_count", 0),
                    "total_amount": item.get("total_amount", 0),
                    "last_order_date": item.get("last_order_date"),
                    "latest_message": item.get("latest_assistant_message")
                }
                items.append(formatted_item)
            
            st.session_state.projects = items
            st.session_state.api_error = None
            return items
        else:
            if st.session_state.api_error != "connection":
                st.error("🔌 バックエンドAPIに接続できません。FastAPIサーバーが起動していることを確認してください。")
                st.session_state.api_error = "connection"
            return st.session_state.projects  # キャッシュされたデータを使用
            
    except APIError as e:
        if st.session_state.api_error != str(e):
            st.error(f"❌ API エラー: {e}")
            st.session_state.api_error = str(e)
        return st.session_state.projects  # キャッシュされたデータを使用
    except Exception as e:
        if st.session_state.api_error != str(e):
            st.error(f"⚠️ 予期しないエラー: {e}")
            st.session_state.api_error = str(e)
        return st.session_state.projects  # キャッシュされたデータを使用

# APIから案件データを取得
items = fetch_items_from_api()

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
                    if st.button("✏️", key=f"edit_{p['id']}", help="編集/削除", use_container_width=True, type="secondary"):
                        open_edit_dialog(p)
                st.markdown(f'<div class="company">{p["company"]}</div>', unsafe_allow_html=True)
                # メタ情報を動的に構築
                meta_info = []
                meta_info.append(f"・最終更新：{_fmt(p.get('updated'))}")
                meta_info.append(f"・作成日：{_fmt(p.get('created'))}")
                meta_info.append(f"・概要：{p.get('summary', '—')}")
                
                # 取引情報がある場合は追加
                if p.get("transaction_count", 0) > 0:
                    meta_info.append(f"・取引履歴：{p['transaction_count']}件")
                    if p.get("total_amount", 0) > 0:
                        meta_info.append(f"・総取引額：¥{p['total_amount']:,.0f}")
                    if p.get("last_order_date"):
                        meta_info.append(f"・最終発注：{format_date(p['last_order_date'])}")
                else:
                    meta_info.append("・取引履歴：未リンク")
                
                # 最新メッセージがある場合は追加
                if p.get("latest_message"):
                    msg_preview = p["latest_message"][:50] + "..." if len(p["latest_message"]) > 50 else p["latest_message"]
                    meta_info.append(f"・最新分析：{msg_preview}")
                
                st.markdown(
                    f'<div class="meta">{"".join([f"{info}<br>" for info in meta_info])}</div>',
                    unsafe_allow_html=True,
                )
                b1, b2 = st.columns(2)
                with b1:
                    if st.button("企業分析", key=f"analysis_{p['id']}", use_container_width=True):
                        st.session_state.selected_project = p
                        _switch_page("企業分析")
                with b2:
                    if st.button("スライド作成", key=f"slides_{p['id']}", use_container_width=True):
                        st.session_state.selected_project = p
                        _switch_page("スライド作成")
