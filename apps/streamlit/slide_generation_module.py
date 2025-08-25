# slide_generation_module.py
# ---------------------------------------------------------
# スライド作成ページ（左右2ペイン＋下段生成）
# - 左：商談の詳細、参考資料アップロード、提案件数＋候補取得ボタン
# - 右：候補一覧（スクロール、チェックで選択）
# - 下：スライド生成（ドラフトJSONプレビュー）
# ---------------------------------------------------------

from __future__ import annotations
from pathlib import Path
from typing import List, Dict, Any
import streamlit as st
import pandas as pd

# 共通スタイル
from lib.styles import apply_main_styles, apply_logo_styles, apply_scroll_script

# APIクライアント
from lib.api import get_api_client, api_available, APIError

# 画像パス
PROJECT_ROOT = Path(__file__).parent.parent.parent
LOGO_PATH = PROJECT_ROOT / "data" / "images" / "otsuka_logo.jpg"


def _ensure_session_defaults() -> None:
    """このページで使うセッションキーを初期化"""
    ss = st.session_state
    ss.setdefault("selected_project", None)      # 案件一覧から遷移時に入る
    ss.setdefault("api_error", None)
    ss.setdefault("slide_meeting_notes", "")
    ss.setdefault("uploaded_files_store", [])    # file_uploaderの保存用（ウィジェットkeyとは別）
    ss.setdefault("product_candidates", [])      # [{id, name, category, price, score, reason}]
    ss.setdefault("selected_products_ids", set())
    ss.setdefault("slide_outline", None)
    ss.setdefault("slide_overview", "")          # 生成前の概要（任意）


def _search_product_candidates(company: str, meeting_notes: str, top_k: int) -> List[Dict[str, Any]]:
    """
    社内商材DBから候補を検索。
    バックエンドAPI想定:
      - api.search_products(company=..., query=..., top_k=...)
        -> [{"id","name","category","price","score","reason"}, ...]
    """
    if not api_available():
        st.warning("APIが利用できないため、商品候補の取得はスキップします。")
        return []
    try:
        api = get_api_client()
        if hasattr(api, "search_products"):
            # 企業分析はバックエンド側で自動付与される前提
            return api.search_products(company=company, query=meeting_notes, top_k=top_k) or []
        else:
            st.info("バックエンドに search_products が見つからないため、ダミー候補を表示します。")
            return [
                {"id": f"DUMMY-{i+1}", "name": f"ダミー商品 {i+1}", "category": "General",
                 "price": (i+1) * 10000, "score": round(0.9 - i*0.03, 2),
                 "reason": "企業分析（自動）と商談内容に基づく暫定理由"}
                for i in range(top_k)
            ]
    except APIError as e:
        st.error(f"❌ 商品候補取得エラー: {e}")
        return []
    except Exception as e:
        st.error(f"⚠️ 予期しないエラー: {e}")
        return []


def _make_outline_preview(company: str, meeting_notes: str, selected_products: List[Dict[str, Any]], overview: str) -> Dict[str, Any]:
    """フロント用のスライド下書き（ドラフト）を組み立て（実生成はバックエンド想定）"""
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


def render_slide_generation_page():
    """スライド作成ページをレンダリング"""
    _ensure_session_defaults()

    # 共通スタイル
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
        st.markdown("")  # 余白
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

    left, right = st.columns([5, 7], gap="large")  # 左＝入力、右＝候補一覧（スクロール）

    # ---- 左ペイン：商談詳細 + 参考資料 + 提案件数 + 候補取得ボタン
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
            key="slide_uploader",  # ← ウィジェットのkey（セッションに書き込まない）
            help="アップロード資料はバックエンドで特徴抽出/要約に利用（想定）。",
        )
        # ウィジェット値は触らず、別キーに保存
        if uploads:
            st.session_state.uploaded_files_store = uploads
            st.success(f"{len(uploads)} ファイルを受け付けました。")
        elif st.session_state.uploaded_files_store:
            st.caption(f"前回アップロード済み: {len(st.session_state.uploaded_files_store)} ファイル")

        # ラベル＋数値入力を密接、右端に「候補を取得」
        bar_left, bar_spacer, bar_right = st.columns([1.2, 0.6, 1.0], gap="small", vertical_alignment="center")
        with bar_left:
            lc, ic = st.columns([0.6, 0.4], gap="small", vertical_alignment="center")
            with lc:
                st.markdown("**提案件数**")
            with ic:
                top_k = st.number_input(
                    label="",
                    min_value=3, max_value=20, value=10, step=1,
                    label_visibility="collapsed",
                    key="top_k_number",
                )
        with bar_right:
            search_btn = st.button("候補を取得", use_container_width=True)

    # ---- 右ペイン：候補一覧（スクロール可能・チェックで選択）
    with right:
        st.markdown("**候補一覧**")

        # 検索実行（左ペインのボタンを押す）
        if search_btn:
            if not company_internal.strip():
                st.error("企業が選択されていません。案件一覧から企業を選んでください。")
            else:
                st.session_state.product_candidates = []
                st.session_state.selected_products_ids = set()
                with st.spinner("社内商材DBから候補を検索中…"):
                    results = _search_product_candidates(
                        company=company_internal,
                        meeting_notes=st.session_state.slide_meeting_notes or "",
                        top_k=int(top_k),
                    )
                st.session_state.product_candidates = results
                if results:
                    st.success(f"候補を {len(results)} 件取得しました。")
                else:
                    st.warning("候補が見つかりませんでした。")

        # テーブル表示（固定高さでスクロール）
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
                hide_index=True,
                height=480,  # ← スクロール高さ
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

            # 選択状態をセッションに反映
            selected_ids = {row["_id"] for _, row in edited.iterrows() if row["選択"]}
            st.session_state.selected_products_ids = selected_ids

            st.caption(f"選択数: {len(selected_ids)}")

    st.divider()

    # ====================== 2. スライド生成 ======================
    st.subheader("2. スライド生成")

    row_l, row_r = st.columns([8, 2], vertical_alignment="center")
    with row_l:
        st.session_state.slide_overview = st.text_input(
            "概説（任意）",
            value=st.session_state.slide_overview or "",
            placeholder="例：在庫最適化を中心に、需要予測と補充計画の連携を提案…",
        )
    with row_r:
        gen_btn = st.button("生成", type="primary", use_container_width=True)

    if gen_btn:
        if not company_internal.strip():
            st.error("企業が選択されていません。")
        else:
            selected = [
                p for p in st.session_state.product_candidates
                if p.get("id") in st.session_state.selected_products_ids
            ]
            outline = _make_outline_preview(
                company_internal,
                st.session_state.slide_meeting_notes or "",
                selected,
                st.session_state.slide_overview or "",
            )
            st.session_state.slide_outline = outline
            st.success("下書きを作成しました。")

    if st.session_state.slide_outline:
        with st.expander("下書きプレビュー（JSON）", expanded=True):
            st.json(st.session_state.slide_outline)
