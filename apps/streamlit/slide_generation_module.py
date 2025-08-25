# slide_generation_module.py
from __future__ import annotations
from pathlib import Path
from typing import List, Dict, Any, Optional
import streamlit as st

from lib.styles import apply_main_styles, apply_logo_styles, apply_scroll_script
from lib.api import get_api_client, api_available, APIError

PROJECT_ROOT = Path(__file__).parent.parent.parent
LOGO_PATH = PROJECT_ROOT / "data" / "images" / "otsuka_logo.jpg"


def _ensure_session_defaults() -> None:
    ss = st.session_state
    ss.setdefault("selected_project", None)
    ss.setdefault("api_error", None)
    ss.setdefault("slide_meeting_notes", "")
    ss.setdefault("slide_uploaded_files", [])
    ss.setdefault("product_candidates", [])
    ss.setdefault("selected_products_ids", set())
    ss.setdefault("slide_outline", None)


def _search_product_candidates(company: str, meeting_notes: str, top_k: int) -> List[Dict[str, Any]]:
    if not api_available():
        st.warning("APIが利用できないため、商品候補の取得はスキップします。")
        return []
    try:
        api = get_api_client()
        if hasattr(api, "search_products"):
            # 企業分析はバックエンドで自動付与される想定
            return api.search_products(company=company, query=meeting_notes, top_k=top_k) or []
        else:
            st.info("バックエンドに search_products が無いためダミー候補を表示します。")
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


def _render_candidate_card(p: Dict[str, Any]) -> bool:
    with st.container(border=True):
        tcol, ccol = st.columns([8, 2])
        with tcol:
            st.markdown(f"**{p.get('name','(No Name)')}**")
            meta = []
            if p.get("category"): meta.append(f"カテゴリ: {p['category']}")
            if p.get("price") is not None: meta.append(f"価格目安: ¥{p['price']:,}")
            if p.get("score") is not None: meta.append(f"スコア: {p['score']}")
            if meta: st.caption(" / ".join(meta))
        with ccol:
            key = f"select_prod_{p.get('id','_')}"
            checked = st.checkbox("選択", key=key, value=p.get("id") in st.session_state.selected_products_ids)
        if p.get("reason"):
            with st.expander("候補理由（根拠）"):
                st.write(p["reason"])
        return checked


def _make_outline_preview(company: str, meeting_notes: str, selected_products: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {
        "title": f"{company} 向け提案資料（ドラフト）",
        "sections": [
            {"h2": "1. アジェンダ", "bullets": ["背景", "課題整理", "提案概要", "導入効果", "導入計画", "次のアクション"]},
            {"h2": "2. 背景", "bullets": [f"{company}の事業概要（要約）", "市場動向・競合状況（抜粋）"]},
            {"h2": "3. 現状の課題（仮説）", "bullets": ["生産性/コスト/品質/スピードの観点から3〜5点"]},
            {"h2": "4. 提案概要", "bullets": ["本提案の目的／狙い", "全体アーキテクチャ（高レベル）"]},
            {"h2": "5. 推奨ソリューション（候補）", "bullets": [f"{len(selected_products)}件の商材候補を整理・比較"]},
            {"h2": "6. 導入効果（定量/定性）", "bullets": ["KPI見込み / 効果試算の方針"]},
            {"h2": "7. 導入スケジュール案", "bullets": ["PoC → 本導入 / 体制・役割分担"]},
            {"h2": "8. 次のアクション", "bullets": ["要件定義ミーティング", "評価用データの準備 など"]},
        ],
        "meeting_notes_digest": meeting_notes[:300] + ("..." if len(meeting_notes) > 300 else ""),
        "products": [
            {"id": p.get("id"), "name": p.get("name"), "category": p.get("category"),
             "price": p.get("price"), "reason": p.get("reason")}
            for p in selected_products
        ],
    }


def _render_company_meta_from_project(pj: Dict[str, Any]) -> None:
    """案件カード由来の企業メタ情報（Expanderで開閉可能、読み取り専用）"""
    if not pj:
        st.info("案件一覧から遷移すると企業メタ情報（作成日/最終更新/概要/取引履歴など）がここに表示されます。")
        return
    with st.expander("企業メタ情報", expanded=True):
        with st.container(border=True):
            info_lines = []
            if pj.get("updated"): info_lines.append(f"・最終更新：{pj['updated']}")
            if pj.get("created"): info_lines.append(f"・作成日：{pj['created']}")
            if pj.get("summary"): info_lines.append(f"・概要：{pj['summary']}")
            tc = pj.get("transaction_count", 0)
            if tc and tc > 0:
                line = f"・取引履歴：{tc}件"
                if pj.get("total_amount", 0) > 0:
                    line += f" / 総取引額：¥{pj['total_amount']:,.0f}"
                if pj.get("last_order_date"):
                    line += f" / 最終発注：{pj['last_order_date']}"
                info_lines.append(line)
            else:
                info_lines.append("・取引履歴：未リンク")
            if pj.get("latest_message"):
                msg_preview = pj["latest_message"][:50] + ("..." if len(pj["latest_message"]) > 50 else "")
                info_lines.append(f"・最新分析：{msg_preview}")
            st.markdown("<br>".join(info_lines), unsafe_allow_html=True)


def render_slide_generation_page():
    _ensure_session_defaults()

    apply_main_styles()
    apply_scroll_script()

    # ヘッダ
    header_col1, header_col2 = st.columns([3, 0.5])
    with header_col1:
        if st.session_state.get("selected_project"):
            pj = st.session_state.selected_project
            st.title(f"スライド作成 - {pj['title']} / {pj['company']}")
            company_default = pj.get("company", "")
        else:
            st.title("スライド作成")
            company_default = ""
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

    # === セクション1: 対象企業（案件選択なし & メタ情報は自動表示） =======================
    st.subheader("1. 対象企業")

    # 対象企業名：黒文字・編集不可（見た目は入力欄風）
    st.markdown("""
        <style>
            .readonly-field {
                border: 1px solid #E6E6E6; border-radius: 8px;
                padding: 0.55rem 0.75rem; background: #FFFFFF;
                color: #111827; font-size: 1rem;
            }
        </style>
    """, unsafe_allow_html=True)
    st.markdown("**対象企業名**")
    st.markdown(f'<div class="readonly-field">{company_default or "—"}</div>', unsafe_allow_html=True)

    # メタ情報（Expanderで開閉）
    _render_company_meta_from_project(st.session_state.get("selected_project"))

    st.divider()

    # === セクション2: 商談の詳細 / 参考資料 ==================================================
    st.subheader("2. 商談の詳細 / 参考資料")
    st.session_state.slide_meeting_notes = st.text_area(
        "商談の詳細（アジェンダ・課題・期待・スコープなど）",
        value=st.session_state.slide_meeting_notes or "",
        height=180,
        placeholder="例：来期の需要予測精度向上と在庫最適化。PoCから段階導入… など"
    )

    uploads = st.file_uploader(
        "参考資料（任意・複数可）",
        type=["pdf", "pptx", "docx", "xlsx", "csv", "txt", "md", "png", "jpg", "jpeg"],
        accept_multiple_files=True,
        help="アップロード資料はバックエンドで特徴抽出/要約に利用（想定）。"
    )
    if uploads:
        st.session_state.slide_uploaded_files = uploads
        st.success(f"{len(uploads)} ファイルを受け付けました。")
    elif st.session_state.slide_uploaded_files:
        st.caption(f"前回アップロード済み: {len(st.session_state.slide_uploaded_files)} ファイル")

    st.divider()

    # === セクション3: 推奨商品候補（社内商材DB） ============================================
    st.subheader("3. 推奨商品候補の取得")

    # 上段：ラベル行 / 下段：コントロール行（高さを完全一致させる）
    label_cols = st.columns([2, 1, 1])
    with label_cols[0]: st.markdown("**最大候補数**")
    with label_cols[1]: st.markdown("**候補を取得**")
    with label_cols[2]: st.markdown("**クリア**")

    control_cols = st.columns([2, 1, 1])
    with control_cols[0]:
        top_k = st.number_input("", min_value=3, max_value=20, value=10, step=1, label_visibility="collapsed")
    with control_cols[1]:
        search_btn = st.button("取得", use_container_width=True)
    with control_cols[2]:
        clear_btn = st.button("クリア", use_container_width=True)

    if clear_btn:
        st.session_state.product_candidates = []
        st.session_state.selected_products_ids = set()
        st.info("候補と選択状態をクリアしました。")

    if search_btn:
        company = (company_default or "").strip()
        if not company:
            st.error("企業名が選択されていません。案件一覧から企業を選んでください。")
        else:
            with st.spinner("社内商材DBから候補を検索中…"):
                results = _search_product_candidates(
                    company=company,
                    meeting_notes=st.session_state.slide_meeting_notes or "",
                    top_k=int(top_k),
                )
            st.session_state.product_candidates = results
            if results:
                st.success(f"候補を {len(results)} 件取得しました。")
            else:
                st.warning("候補が見つかりませんでした。")

    if st.session_state.product_candidates:
        st.caption("提案したいものをチェックしてください。")
        changed_any = False
        for p in st.session_state.product_candidates:
            checked = _render_candidate_card(p)
            pid = p.get("id")
            if checked and pid not in st.session_state.selected_products_ids:
                st.session_state.selected_products_ids.add(pid); changed_any = True
            elif not checked and pid in st.session_state.selected_products_ids:
                st.session_state.selected_products_ids.remove(pid); changed_any = True
        if changed_any:
            st.toast(f"選択数: {len(st.session_state.selected_products_ids)}")

    st.divider()

    # === セクション4: スライド下書き生成（プレビュー） =======================================
    st.subheader("4. スライド下書きを作成")
    gen_col1, gen_col2 = st.columns([1, 3])
    with gen_col1:
        gen_btn = st.button("スライド下書きを作成する", type="primary")
    with gen_col2:
        st.caption("※現在はフロントのプレビューのみ。実生成はバックエンド/LLMへ差し替え予定。")

    if gen_btn:
        company = (company_default or "").strip()
        if not company:
            st.error("企業名が選択されていません。")
        else:
            selected = [p for p in st.session_state.product_candidates
                        if p.get("id") in st.session_state.selected_products_ids]
            outline = _make_outline_preview(company, st.session_state.slide_meeting_notes or "", selected)
            st.session_state.slide_outline = outline
            st.success("下書きを作成しました。")

    if st.session_state.slide_outline:
        with st.expander("下書きプレビュー（JSON）", expanded=True):
            st.json(st.session_state.slide_outline)
