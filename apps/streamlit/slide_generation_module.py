# slide_generation_module.py
# ---------------------------------------------------------
# スライド作成ページ（左右2ペイン＋下段生成）
# ---------------------------------------------------------

from __future__ import annotations
from pathlib import Path
from typing import List, Dict, Any, Tuple
import streamlit as st
import pandas as pd

from lib.styles import apply_main_styles, apply_logo_styles, apply_scroll_script
from lib.api import get_api_client, api_available, APIError

PROJECT_ROOT = Path(__file__).parent.parent.parent
LOGO_PATH = PROJECT_ROOT / "data" / "images" / "otsuka_logo.jpg"


def _ensure_session_defaults() -> None:
    ss = st.session_state
    ss.setdefault("selected_project", None)
    ss.setdefault("api_error", None)
    ss.setdefault("slide_meeting_notes", "")
    ss.setdefault("uploaded_files_store", [])       # file_uploader保存用（widget keyとは別）
    ss.setdefault("product_candidates", [])         # [{id, name, category, price, score, reason}]
    ss.setdefault("selected_products_ids", set())
    ss.setdefault("slide_outline", None)
    ss.setdefault("slide_overview", "")
    ss.setdefault("top_k_number", 10)               # 3〜20


def _search_product_candidates(company: str, meeting_notes: str, top_k: int) -> Tuple[List[Dict[str, Any]], List[Tuple[str, str]]]:
    """候補検索。戻り値: (results, notices[(level, msg)])"""
    notices: List[Tuple[str, str]] = []

    if not api_available():
        notices.append(("warning", "APIが利用できないため、商品候補の取得はスキップしました。"))
        return [], notices

    try:
        api = get_api_client()
        if hasattr(api, "search_products"):
            results = api.search_products(company=company, query=meeting_notes, top_k=top_k) or []
            return results, notices
        else:
            # 未実装フォールバック：ダミー
            results = [
                {"id": f"DUMMY-{i+1}", "name": f"ダミー商品 {i+1}", "category": "General",
                 "price": (i+1) * 10000, "score": round(0.9 - i*0.03, 2),
                 "reason": "企業分析（自動）と商談内容に基づく暫定理由"}
                for i in range(top_k)
            ]
            notices.append(("info", "バックエンドに search_products が見つからないため、ダミー候補を表示します。"))
            return results, notices
    except APIError as e:
        notices.append(("error", f"❌ 商品候補取得エラー: {e}"))
        return [], notices
    except Exception as e:
        notices.append(("error", f"⚠️ 予期しないエラー: {e}"))
        return [], notices


def _make_outline_preview(company: str, meeting_notes: str, selected_products: List[Dict[str, Any]], overview: str) -> Dict[str, Any]:
    return {
        "title": f"{company} 向け提案資料（ドラフト）",
        "overview": overview,
        "sections": [
            {"h2": "1. アジェンダ", "bullets": ["背景", "課題整理", "提案概要", "導入効果", "導入計画", "次のアクション"]},
            {"h2": "2. 背景", "bullets": [f"{company}の事業概要（要約）", "市場動向・競合状況（抜粋）"]},
            {"h2": "3. 現状の課題（仮説）", "bullets": ["生産性/コスト/品質/スピードの観点から3〜5点"]},
            {"h2": "4. 提案概要", "bullets": ["本提案の目的／狙い", "全体アーキテクチャ（高レベル）"]},
            {"h2": "5. 推奨ソリューション（候補）", "bullets": [f"{len(selected_products)}件の商材候補を整理・比較"]},
            {"h2": "6. 導入効果（定量/定性）", "bullets": ["KPI見込み / 効果試算の方針"]},
            {"h2": "7. 導入スケジュール案", "bullets": ["PoC → 本導入 / 体制・役割分担"]},
        ],
        "meeting_notes_digest": meeting_notes[:300] + ("..." if len(meeting_notes) > 300 else ""),
        "products": [
            {"id": p.get("id"), "name": p.get("name"), "category": p.get("category"),
             "price": p.get("price"), "reason": p.get("reason")}
            for p in selected_products
        ],
    }


# --- top_kの±調整（on_clickで使用） ---
def _bump_top_k(delta: int) -> None:
    v = int(st.session_state.get("top_k_number", 10))
    st.session_state.top_k_number = max(3, min(20, v + delta))


def render_slide_generation_page():
    _ensure_session_defaults()
    apply_main_styles()
    apply_scroll_script()

    # ヘッダ
    header_col1, header_col2 = st.columns([3, 0.5])
    with header_col1:
        pj = st.session_state.get("selected_project")
        if pj:
            st.title(f"スライド作成 - {pj['title']} / {pj['company']}")
            company_internal = pj.get("company", "")
        else:
            st.title("スライド作成")
            company_internal = ""
    with header_col2:
        st.markdown("")
        try:
            apply_logo_styles()
            st.image(str(LOGO_PATH), width=160, use_container_width=False)
        except FileNotFoundError:
            st.info(f"ロゴ画像が見つかりません: {LOGO_PATH}")
        except Exception as e:
            st.warning(f"ロゴの読み込みエラー: {e}")

    if st.button("← 案件一覧に戻る"):
        st.session_state.current_page = "案件一覧"
        st.session_state.page_changed = True
        st.rerun()

    # ====================== 1. 商品提案（左右2ペイン） ======================
    st.subheader("1. 商品提案")

    left, right = st.columns([5, 7], gap="large")  # 左=入力、右=候補一覧（スクロール）

    section_notices: List[Tuple[str, str]] = []

    # ---- 左ペイン：商談詳細・資料・提案件数・取得ボタン
    with left:
        st.text_area(
            "商談の詳細",
            key="slide_meeting_notes",
            height=160,
            placeholder="例：来期の需要予測精度向上と在庫最適化。PoCから段階導入… など",
        )

        uploads = st.file_uploader(
            "参考資料（任意）",
            type=["pdf", "pptx", "docx", "xlsx", "csv", "txt", "md", "png", "jpg", "jpeg"],
            accept_multiple_files=True,
            key="slide_uploader",
            help="アップロード資料はバックエンドで特徴抽出/要約に利用（想定）。",
        )
        if uploads:
            st.session_state.uploaded_files_store = uploads
            st.success(f"{len(uploads)} ファイルを受け付けました。")
        elif st.session_state.uploaded_files_store:
            st.caption(f"前回アップロード済み: {len(st.session_state.uploaded_files_store)} ファイル")

        # ラベル＋数値入力＋±ボタン（右端に取得）
        bar_left, bar_spacer, bar_right = st.columns([1.8, 0.6, 1.0], gap="small", vertical_alignment="center")
        with bar_left:
            lc, ic, dec_c, inc_c = st.columns([0.45, 0.40, 0.075, 0.075], gap="small", vertical_alignment="center")
            with lc:
                st.markdown("**提案件数**")
            with ic:
                # key のみ指定（値はセッションがソース・オブ・トゥルース）
                st.number_input(
                    label="",
                    min_value=3, max_value=20, step=1,
                    key="top_k_number",
                    label_visibility="collapsed",
                )
            with dec_c:
                st.button("−", key="topk_dec", use_container_width=True, on_click=_bump_top_k, kwargs={"delta": -1})
            with inc_c:
                st.button("+", key="topk_inc", use_container_width=True, on_click=_bump_top_k, kwargs={"delta": +1})

        with bar_right:
            search_btn = st.button("候補を取得", use_container_width=True)

    # --- 取得処理は右ペインの表描画「前」に実行（1回クリックで表示されるように）
    if search_btn:
        if not company_internal.strip():
            section_notices.append(("error", "企業が選択されていません。案件一覧から企業を選んでください。"))
        else:
            st.session_state.product_candidates = []
            st.session_state.selected_products_ids = set()
            with st.spinner("社内商材DBから候補を検索中…"):
                results, notes = _search_product_candidates(
                    company=company_internal,
                    meeting_notes=st.session_state.slide_meeting_notes or "",
                    top_k=int(st.session_state.top_k_number),
                )
            st.session_state.product_candidates = results
            section_notices.extend(notes)
            if results:
                section_notices.append(("success", f"候補を {len(results)} 件取得しました。"))
            else:
                section_notices.append(("warning", "候補が見つかりませんでした。"))

    # ---- 右ペイン：候補一覧（data_editor, スクロール, 1クリックで反映）
    with right:
        st.markdown("**候補一覧**")

        if st.session_state.product_candidates:
            df = pd.DataFrame([
                {
                    "選択": (p.get("id") in st.session_state.selected_products_ids),
                    "商品名": p.get("name"),
                    "カテゴリ": p.get("category"),
                    "価格": p.get("price"),
                    "スコア": p.get("score"),
                    "理由": p.get("reason"),
                    "_id": p.get("id"),
                }
                for p in st.session_state.product_candidates
            ])

            edited = st.data_editor(
                df,
                key="candidates_editor",          # ← keyを付与
                hide_index=True,
                height=480,
                use_container_width=True,
                column_config={
                    "選択": st.column_config.CheckboxColumn("選択", help="提案に含める場合チェック"),
                    "価格": st.column_config.NumberColumn("価格", format="¥%d", disabled=True),
                    "スコア": st.column_config.NumberColumn("スコア", step=0.01, disabled=True),
                    "商品名": st.column_config.TextColumn("商品名", disabled=True),
                    "カテゴリ": st.column_config.TextColumn("カテゴリ", disabled=True),
                    "理由": st.column_config.TextColumn("理由", disabled=True),
                    "_id": st.column_config.TextColumn("_id", disabled=True),
                },
                disabled=["商品名", "カテゴリ", "価格", "スコア", "理由", "_id"],
            )

            # 1クリックで反映：返ってきたeditedから即セッションに反映
            selected_ids = {row["_id"] for _, row in edited.iterrows() if row["選択"]}
            if selected_ids != st.session_state.selected_products_ids:
                st.session_state.selected_products_ids = selected_ids
