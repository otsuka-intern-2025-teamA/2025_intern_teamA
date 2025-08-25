# slide_generation_module.py
# ---------------------------------------------------------
# スライド作成ページ（左右2ペイン＋下段生成）
# LLM推薦（OpenAI/Azure） + 任意で既存APIフォールバック
# ＊候補一覧は LLMの返答をそのまま表示（表・選択は無し）
# ---------------------------------------------------------

from __future__ import annotations
from pathlib import Path
from typing import List, Dict, Any, Tuple
import streamlit as st

from lib.styles import apply_main_styles, apply_logo_styles, apply_scroll_script
from lib.api import get_api_client, api_available, APIError

# LLM 推薦
from lib.product_recommend.llm_recommend import recommend_products

# パス設定
PROJECT_ROOT = Path(__file__).parent.parent.parent
DATASET_DIR = PROJECT_ROOT / "data" / "csv" / "products" / "DatasetA"
LOGO_PATH = PROJECT_ROOT / "data" / "images" / "otsuka_logo.jpg"


def _ensure_session_defaults() -> None:
    ss = st.session_state
    ss.setdefault("selected_project", None)
    ss.setdefault("api_error", None)
    ss.setdefault("slide_meeting_notes", "")
    ss.setdefault("uploaded_files_store", [])       # file_uploader 保存用（widget keyとは別）
    ss.setdefault("product_candidates", [])         # List[ProductRecommendation] or List[dict]
    ss.setdefault("slide_outline", None)
    ss.setdefault("slide_overview", "")
    ss.setdefault("top_k_number", 10)               # 3〜20


def _bump_top_k(delta: int) -> None:
    v = int(st.session_state.get("top_k_number", 10))
    st.session_state.top_k_number = max(3, min(20, v + delta))


def _cand_to_dict(p: Any) -> Dict[str, Any]:
    """ProductRecommendation/dataclass でも dict でも同じ形に正規化"""
    if isinstance(p, dict):
        return {
            "id": p.get("id"),
            "name": p.get("name"),
            "category": p.get("category"),
            "price": p.get("price"),
            "score": p.get("score"),
            "reason": p.get("reason"),
        }
    # dataclass / オブジェクト想定
    return {
        "id": getattr(p, "id", None),
        "name": getattr(p, "name", None),
        "category": getattr(p, "category", None),
        "price": getattr(p, "price", None),
        "score": getattr(p, "score", None),
        "reason": getattr(p, "reason", None),
    }


def _search_product_candidates_backend(company: str, meeting_notes: str, top_k: int) -> Tuple[List[Dict[str, Any]], List[Tuple[str, str]]]:
    """バックエンドAPIがあればフォールバックで検索"""
    notices: List[Tuple[str, str]] = []
    if not api_available():
        notices.append(("warning", "APIが利用できないため、バックエンド検索はスキップしました。"))
        return [], notices
    try:
        api = get_api_client()
        if hasattr(api, "search_products"):
            results = api.search_products(company=company, query=meeting_notes, top_k=top_k) or []
            return results, notices
        else:
            notices.append(("info", "バックエンドに search_products が見つからないため、フォールバックできません。"))
            return [], notices
    except APIError:
        notices.append(("error", "商品候補取得エラー（バックエンド）"))
        return [], notices
    except Exception:
        notices.append(("error", "商品候補取得で不明なエラー（バックエンド）"))
        return [], notices


def _make_outline_preview(company: str, meeting_notes: str, products: List[Dict[str, Any]], overview: str) -> Dict[str, Any]:
    """スライド下書きの簡易構成を生成（products は dict 正規化済みを想定）"""
    return {
        "title": f"{company} 向け提案資料（ドラフト）",
        "overview": overview,
        "sections": [
            {"h2": "1. アジェンダ", "bullets": ["背景", "課題整理", "提案概要", "導入効果", "導入計画", "次のアクション"]},
            {"h2": "2. 背景", "bullets": [f"{company}の事業概要（要約）", "市場動向・競合状況（抜粋）"]},
            {"h2": "3. 現状の課題（仮説）", "bullets": ["生産性/コスト/品質/スピードの観点から3〜5点"]},
            {"h2": "4. 提案概要", "bullets": ["本提案の目的／狙い", "全体アーキテクチャ（高レベル）"]},
            {"h2": "5. 推奨ソリューション（候補）", "bullets": [f"{len(products)}件の商材候補を整理・比較"]},
            {"h2": "6. 導入効果（定量/定性）", "bullets": ["KPI見込み / 効果試算の方針"]},
            {"h2": "7. 導入スケジュール案", "bullets": ["PoC → 本導入 / 体制・役割分担"]},
        ],
        "meeting_notes_digest": meeting_notes[:300] + ("..." if len(meeting_notes) > 300 else ""),
        "products": [
            {"id": p.get("id"), "name": p.get("name"), "category": p.get("category"),
             "price": p.get("price"), "reason": p.get("reason")}
            for p in products
        ],
    }


def _fetch_analysis_chat_history_text(project_id: Any) -> str:
    """同案件の企業分析チャット履歴を取得してテキスト化（最大2000文字程度）"""
    if not api_available():
        return ""
    try:
        api = get_api_client()
        for name in ("get_company_analysis_chat_history", "get_messages", "get_chat_history"):
            if hasattr(api, name):
                msgs = getattr(api, name)(project_id)
                texts: List[str] = []
                if isinstance(msgs, list):
                    for m in msgs[-30:]:
                        try:
                            role = (m.get("role") or "").strip()
                            content = (m.get("content") or "").strip()
                            if content:
                                texts.append(f"[{role}] {content}")
                        except Exception:
                            pass
                elif isinstance(msgs, str):
                    texts = [msgs]
                return "\n".join(texts)[-2000:]
        return ""
    except Exception:
        return ""


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
            project_id = pj.get("id")
        else:
            st.title("スライド作成")
            company_internal = ""
            project_id = None
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

    # ====================== 1. 商品提案 ======================
    st.subheader("1. 商品提案")
    left, right = st.columns([5, 7], gap="large")
    section_notices: List[Tuple[str, str]] = []

    # 左ペイン：入力
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
            help="添付は特徴抽出に使用（現状は任意・未使用。将来バージョンで活用予定）。",
        )
        if uploads:
            st.session_state.uploaded_files_store = uploads
            st.success(f"{len(uploads)} ファイルを受け付けました。")
        elif st.session_state.uploaded_files_store:
            st.caption(f"前回アップロード済み: {len(st.session_state.uploaded_files_store)} ファイル")

        # 提案件数と取得ボタン（水平揃え）
        bar_left, bar_spacer, bar_right = st.columns([1.8, 0.6, 1.0], gap="small", vertical_alignment="center")
        with bar_left:
            lc, ic, dec_c, inc_c = st.columns([0.45, 0.40, 0.075, 0.075], gap="small", vertical_alignment="center")
            with lc:
                st.markdown("**提案件数**")
            with ic:
                st.number_input(label="", min_value=3, max_value=20, step=1, key="top_k_number", label_visibility="collapsed")
            with dec_c:
                st.button("−", key="topk_dec", use_container_width=True, on_click=_bump_top_k, kwargs={"delta": -1})
            with inc_c:
                st.button("+", key="topk_inc", use_container_width=True, on_click=_bump_top_k, kwargs={"delta": +1})
        with bar_right:
            search_btn = st.button("候補を取得", use_container_width=True)

    # 取得処理
    if search_btn:
        if not company_internal.strip():
            section_notices.append(("error", "企業が選択されていません。案件一覧から企業を選んでください。"))
        else:
            # --- デバッグ情報（鍵は出さない） ---
            import os
            st.info(
                f"**【デバッグ情報】**\n"
                f"- **Endpoint:** `{os.getenv('AZURE_OPENAI_ENDPOINT')}`\n"
                f"- **Deployment Name:** `{os.getenv('AZURE_OPENAI_CHAT_DEPLOYMENT') or os.getenv('DEFAULT_MODEL')}`\n"
                f"- **API Version:** `{os.getenv('API_VERSION') or ''}`"
            )

            # 企業分析のチャット履歴（同案件）
            chat_text = _fetch_analysis_chat_history_text(project_id) if project_id else ""
            try:
                results = recommend_products(
                    dataset_dir=DATASET_DIR,
                    company=company_internal,
                    meeting_notes=st.session_state.slide_meeting_notes or "",
                    chat_history_text=chat_text,
                    top_k=int(st.session_state.top_k_number),
                )
                st.session_state.product_candidates = results
                if results:
                    section_notices.append(("success", f"候補を {len(results)} 件取得しました。"))
                else:
                    # 任意: バックエンドへフォールバック
                    be, be_notes = _search_product_candidates_backend(
                        company=company_internal,
                        meeting_notes=st.session_state.slide_meeting_notes or "",
                        top_k=int(st.session_state.top_k_number),
                    )
                    st.session_state.product_candidates = be
                    section_notices.extend(be_notes)
                    if be:
                        section_notices.append(("success", f"候補を {len(be)} 件取得しました。"))
                    else:
                        section_notices.append(("warning", "候補が見つかりませんでした。"))
            except Exception as e:
                section_notices.append(("error", f"LLM推薦の初期化に失敗しました（設定や依存関係をご確認ください）。\n\n詳細: {e}"))
                # 最後にバックエンドへ
                be, be_notes = _search_product_candidates_backend(
                    company=company_internal,
                    meeting_notes=st.session_state.slide_meeting_notes or "",
                    top_k=int(st.session_state.top_k_number),
                )
                st.session_state.product_candidates = be
                section_notices.extend(be_notes)

    # 右ペイン：LLM返答をそのまま表示（まず dict に正規化）
    with right:
        st.markdown("**候補（LLMの返答）**")
        raw_recs = st.session_state.product_candidates or []
        recs = [_cand_to_dict(p) for p in raw_recs]  # ← ここで正規化
        if recs:
            for i, p in enumerate(recs, 1):
                name = p.get("name") or ""
                cat = p.get("category") or "—"
                price = p.get("price")
                price_s = f"¥{int(price):,}" if isinstance(price, (int, float)) else "—"
                score = p.get("score")
                score_s = f"{score:.2f}" if isinstance(score, (int, float)) else "—"
                reason = p.get("reason") or ""
                pid = p.get("id") or ""
                st.markdown(
                    f"{i}. **{name}** 〔{cat} / {price_s}〕  \n"
                    f"　・理由：{reason}  \n"
                    f"　・信頼度：{score_s}  \n"
                    f"　・ID：`{pid}`"
                )
            with st.expander("LLM返答のJSONを見る"):
                st.json(recs)
        else:
            st.info("候補がありません。左側で『候補を取得』を実行してください。")

    # セクション末尾に通知
    if section_notices:
        with st.container():
            for level, msg in section_notices:
                if level == "success":
                    st.success(msg)
                elif level == "info":
                    st.info(msg)
                elif level == "warning":
                    st.warning(msg)
                elif level == "error":
                    st.error(msg)
                else:
                    st.write(msg)

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
        if not (pj and company_internal.strip()):
            st.error("企業が選択されていません。")
        else:
            # 返ってきた候補を全件採用（dict 正規化後を利用）
            selected = [_cand_to_dict(p) for p in (st.session_state.product_candidates or [])]
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
