# slide_generation_module.py
# ---------------------------------------------------------
# スライド作成ページ（サイドバー追加版）
# - サイドバー：ロゴ／案件一覧へ戻る（左下固定）／企業名／提案件数／履歴参照件数／商材データセット選択／クリア
# - 本文：上段ヘッダ（左＝見出し／右＝候補取得ボタン）、
#          左＝商談詳細＆参考資料アップ、右＝LLM提案（text_areaでスクロール可能）、
#          下段＝生成とドラフトJSON
# - バックエンドAPI search_products が無い/未対応でも、CSV＋チャット履歴の簡易スコアでフォールバック
# - ★ 右ペインは text_area（読み取り専用）で確実に「枠内スクロール」
# ---------------------------------------------------------

from __future__ import annotations
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import re
from datetime import datetime

import streamlit as st
import pandas as pd

# 共通スタイル
from lib.styles import (
    apply_main_styles,
    apply_chat_scroll_script,
    apply_title_styles,
    apply_company_analysis_page_styles,   # サイドバー圧縮/ロゴカード/下寄せCSSを流用
    apply_slide_generation_page_styles,
    render_sidebar_logo_card,
    render_slide_generation_title,        # タイトル描画（h1.slide-generation-title）
)

# 既存の企業分析用LLM関数
from lib.company_analysis.llm import company_briefing_without_web_search

# APIクライアント
from lib.api import get_api_client, api_available, APIError

# AI Agent для генерации презентаций
from lib.slide_generator import slide_generator

# 画像/データパス
PROJECT_ROOT = Path(__file__).parent.parent.parent
LOGO_PATH = PROJECT_ROOT / "data" / "images" / "otsuka_logo.jpg"
ICON_PATH = PROJECT_ROOT / "data" / "images" / "otsuka_icon.png"
PRODUCTS_DIR = PROJECT_ROOT / "data" / "csv" / "products"


# =========================
# セッション初期化
# =========================
def _ensure_session_defaults() -> None:
    ss = st.session_state
    ss.setdefault("selected_project", None)       # 案件一覧から遷移時に入る
    ss.setdefault("api_error", None)
    ss.setdefault("slide_meeting_notes", "")
    ss.setdefault("uploaded_files_store", [])     # file_uploaderの保存用
    ss.setdefault("product_candidates", [])       # [{id, name, category, price, score, reason}]
    ss.setdefault("slide_outline", None)
    ss.setdefault("slide_overview", "")
    ss.setdefault("slide_history_reference_count", 3)  # 直近N往復参照（デフォ3）
    ss.setdefault("slide_top_k", 10)                   # 提案件数（デフォ10）
    ss.setdefault("slide_products_dataset", "Auto")    # 商材データセット選択
    ss.setdefault("llm_proposal_text", "")             # LLMの出力


# =========================
# データセット/コンテキスト収集
# =========================
def _list_product_datasets() -> List[str]:
    """productsディレクトリ配下のサブフォルダ名を列挙（Autoを先頭）"""
    if not PRODUCTS_DIR.exists():
        return ["Auto"]
    ds = ["Auto"]
    for p in PRODUCTS_DIR.iterdir():
        if p.is_dir():
            ds.append(p.name)
    return ds


def _gather_messages_context(item_id: Optional[str], history_n: int) -> str:
    """企業分析の直近N往復（=2N発言）をまとめて文字列化"""
    if not (item_id and api_available()):
        return ""
    try:
        api = get_api_client()
        msgs = api.get_item_messages(item_id) or []
        take = min(len(msgs), history_n * 2)
        recent = msgs[-take:] if take > 0 else []
        ctx_lines = []
        for m in recent:
            role = m.get("role", "assistant")
            role_j = "ユーザー" if role == "user" else "アシスタント"
            ctx_lines.append(f"{role_j}: {m.get('content','')}")
        return "\n".join(ctx_lines)
    except Exception:
        return ""


def _list_uploaded_names(files: List[Any]) -> List[str]:
    names = []
    for f in files or []:
        try:
            names.append(getattr(f, "name", "uploaded_file"))
        except Exception:
            pass
    return names


def _load_products_from_csv(dataset: str) -> pd.DataFrame:
    """
    商材CSVをロード（存在カラムが無ければ作成）
    期待カラム: id(無ければ生成), name, category, price, description, tags
    """
    frames: List[pd.DataFrame] = []
    if not PRODUCTS_DIR.exists():
        return pd.DataFrame()

    def _read_csvs(folder: Path):
        for csvp in folder.glob("*.csv"):
            try:
                df = pd.read_csv(csvp)
                for col in ["name", "category", "price", "description", "tags"]:
                    if col not in df.columns:
                        df[col] = None
                if "id" not in df.columns:
                    df["id"] = [f"{csvp.stem}-{i+1}" for i in range(len(df))]
                frames.append(df[["id", "name", "category", "price", "description", "tags"]])
            except Exception:
                continue

    if dataset == "Auto":
        for sub in PRODUCTS_DIR.iterdir():
            if sub.is_dir():
                _read_csvs(sub)
        _read_csvs(PRODUCTS_DIR)
    else:
        target = PRODUCTS_DIR / dataset
        if target.exists() and target.is_dir():
            _read_csvs(target)

    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


# =========================
# 検索フォールバック（簡易スコアリング）
# =========================
def _simple_tokenize(text: str) -> List[str]:
    text = str(text or "").lower()
    text = re.sub(r"[^a-z0-9\u3040-\u30ff\u4e00-\u9fff]+", " ", text)
    toks = text.split()
    return [t for t in toks if len(t) >= 2]


def _fallback_rank_products(
    notes: str,
    messages_ctx: str,
    products_df: pd.DataFrame,
    top_k: int
) -> List[Dict[str, Any]]:
    """商談メモ＋履歴の語句一致で素朴にスコアリング"""
    if products_df.empty:
        return []

    query_text = (notes or "") + "\n" + (messages_ctx or "")
    q_tokens = _simple_tokenize(query_text)
    if not q_tokens:
        out = []
        for _, row in products_df.head(top_k).iterrows():
            out.append({
                "id": row.get("id"),
                "name": row.get("name"),
                "category": row.get("category"),
                "price": row.get("price"),
                "score": 0.0,
                "reason": "キーワード不足のため先頭候補（暫定）",
            })
        return out

    def _row_text(row) -> str:
        return " ".join([
            str(row.get("name") or ""),
            str(row.get("category") or ""),
            str(row.get("description") or ""),
            str(row.get("tags") or ""),
        ]).lower()

    scored: List[Tuple[float, Dict[str, Any]]] = []
    for _, row in products_df.iterrows():
        t = _row_text(row)
        score = 0.0
        for tok in q_tokens:
            if tok in t:
                score += 1.0
        reason = f"一致語句数={int(score)}" if score > 0 else "一致なし（低スコア）"
        scored.append((score, {
            "id": row.get("id"),
            "name": row.get("name"),
            "category": row.get("category"),
            "price": row.get("price"),
            "score": round(float(score), 2),
            "reason": reason,
        }))

    scored.sort(key=lambda x: (x[0], str(x[1]["name"]).lower()), reverse=True)
    return [d for _, d in scored[:top_k]]


# =========================
# LLM プロンプト生成＆実行
# =========================
def _build_llm_prompt_for_proposals(
    company: str,
    meeting_notes: str,
    messages_ctx: str,
    uploads_names: List[str],
    candidates: List[Dict[str, Any]],
    want: int,
) -> str:
    cand_lines = []
    for c in candidates:
        cand_lines.append(
            f"- name: {c.get('name')} | category: {c.get('category')} | price: {c.get('price')} | hint: {c.get('reason')}"
        )
    uploads_line = ", ".join(uploads_names) if uploads_names else "（なし）"
    ctx_block = messages_ctx.strip() or "（直近のチャット履歴なし）"

    prompt = f"""あなたはB2B提案のプリセールスコンサルタントです。
以下の情報を使い、**{company}** 向けの提案商材を **最大 {want} 件**、日本語Markdownで出力してください。

# 依頼
- 「提案の要旨（2〜3行）」を最初に。
- その後に 「推奨商材（max {want} 件）」を、**箇条書き**で以下の形式で詳述:
  - **商材名**（カテゴリ、概算価格） — この案件での適合理由（業務インパクト/導入容易性/前提条件など）
- 最後に「次のアクション（打ち手案）」として、2〜3項目。

# 入力（商談メモ抜粋）
{meeting_notes.strip() or "（未入力）"}

# 参考資料（ファイル名）
{uploads_line}

# 直近チャット履歴（企業分析）
{ctx_block}

# 候補カタログ（社内商材）
{chr(10).join(cand_lines)}

# 注意
- 候補カタログの中から選び、必要があれば複数を組み合わせてもよい。
- カタログに無い要素技術や一般論に依存しすぎないこと。
- 誇張を避け、根拠ベースで具体的に。
- 出力は**日本語Markdown**のみ。前置きやメタコメントは禁止。
"""
    return prompt


def _run_llm_proposal(
    company: str,
    meeting_notes: str,
    item_id: Optional[str],
    history_n: int,
    candidates: List[Dict[str, Any]],
    uploads: List[Any],
    want: int,
) -> str:
    messages_ctx = _gather_messages_context(item_id, history_n)
    uploads_names = _list_uploaded_names(uploads)
    prompt = _build_llm_prompt_for_proposals(
        company=company,
        meeting_notes=meeting_notes,
        messages_ctx=messages_ctx,
        uploads_names=uploads_names,
        candidates=candidates,
        want=want,
    )
    try:
        result = company_briefing_without_web_search(company, prompt, "")
        return str(result)
    except Exception as e:
        return f"LLM実行でエラーが発生しました: {e}"


# =========================
# 候補検索（API or フォールバック）
# =========================
def _search_product_candidates(
    company: str,
    item_id: Optional[str],
    meeting_notes: str,
    top_k: int,
    history_n: int,
    dataset: str,
    uploaded_files: List[Any],
) -> List[Dict[str, Any]]:
    if api_available():
        try:
            api = get_api_client()
            if hasattr(api, "search_products"):
                try:
                    return api.search_products(
                        company=company,
                        query=meeting_notes,
                        top_k=top_k,
                        context=_gather_messages_context(item_id, history_n),
                        dataset=dataset,
                        uploads=", ".join(_list_uploaded_names(uploaded_files)),
                    ) or []
                except TypeError:
                    return api.search_products(company=company, query=meeting_notes, top_k=top_k) or []
        except APIError as e:
            st.error(f"❌ 商品候補取得エラー: {e}")
        except Exception:
            pass

    products_df = _load_products_from_csv(dataset)
    return _fallback_rank_products(
        notes=meeting_notes,
        messages_ctx=_gather_messages_context(item_id, history_n),
        products_df=products_df,
        top_k=top_k,
    )


# =========================
# ドラフト作成
# =========================
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


def _get_company_report_from_messages(item_id: Optional[str]) -> str:
    """Получает отчет о компании из сообщений в базе данных"""
    if not item_id or not api_available():
        return "企業レポート情報が利用できません。"
    
    try:
        api = get_api_client()
        # Получаем последние сообщения для анализа
        messages = api.get_item_messages(item_id, limit=20)
        
        if not messages:
            return "メッセージ履歴がありません。"
        
        # Собираем контекст из сообщений
        report_parts = []
        for msg in messages:
            if msg.get("role") == "assistant":
                content = msg.get("content", "")
                if content and len(content) > 50:  # Фильтруем короткие сообщения
                    report_parts.append(content)
        
        if report_parts:
            # Объединяем последние 3 сообщения ассистента
            return "\n\n".join(report_parts[-3:])
        else:
            return "企業分析の結果が利用できません。"
            
    except Exception as e:
        st.warning(f"企業レポートの取得でエラーが発生しました: {str(e)}")
        return "企業レポートの取得中にエラーが発生しました。"


# =========================
# メイン描画
# =========================
def render_slide_generation_page():
    """スライド作成ページをレンダリング（右ペインは text_area で枠内スクロール）"""
    _ensure_session_defaults()

    try:
        st.set_page_config(
            page_title="スライド作成",
            page_icon=str(ICON_PATH),
            layout="wide",
            initial_sidebar_state="expanded",
        )
    except Exception:
        pass

    # スタイル
    apply_main_styles(hide_sidebar=False, hide_header=True)
    apply_chat_scroll_script()
    apply_title_styles()
    apply_company_analysis_page_styles()  # サイドバー共通
    apply_slide_generation_page_styles()  # タイトル位置など

    # 案件コンテキスト
    pj = st.session_state.get("selected_project")
    if pj:
        title_text = f"スライド作成 - {pj['title']} / {pj['company']}"
        company_internal = pj.get("company", "")
        item_id = pj.get("id")
    else:
        title_text = "スライド作成"
        company_internal = ""
        item_id = None

    # ---------- サイドバー ----------
    with st.sidebar:
        render_sidebar_logo_card(LOGO_PATH)

        st.markdown("### 設定")
        st.text_input("企業名", value=company_internal, key="slide_company_input", disabled=True)

        st.session_state.slide_top_k = st.number_input(
            "提案件数",
            min_value=3, max_value=20, value=st.session_state.slide_top_k, step=1,
            key="slide_top_k_input",
        )

        st.session_state.slide_history_reference_count = st.selectbox(
            "履歴参照件数（往復）",
            options=list(range(1, 11)),
            index=max(0, st.session_state.slide_history_reference_count - 1),
            key="slide_history_count_select",
            help="企業分析のチャット履歴の直近N往復を文脈として使用",
        )

        datasets = _list_product_datasets()
        st.session_state.slide_products_dataset = st.selectbox(
            "商材データセット",
            options=datasets,
            index=datasets.index(st.session_state.slide_products_dataset) if st.session_state.slide_products_dataset in datasets else 0,
            key="slide_products_dataset_select",
            help="data/csv/products/ 配下のフォルダ。Autoは自動選択。",
        )

        st.markdown("---")
        st.markdown("### AI設定")
        
        # API настройки
        use_tavily_api = st.checkbox(
            "TAVILY API使用",
            value=False,
            key="use_tavily_api",
            help="TAVILY APIを使用して商品情報を強化"
        )
        
        use_gpt_api = st.checkbox(
            "GPT API使用",
            value=False,
            key="use_gpt_api",
            help="GPT APIを使用してスライド内容を生成"
        )
        
        if use_tavily_api:
            tavily_uses = st.number_input(
                "TAVILY API呼び出し回数（商品ごと）",
                min_value=1,
                max_value=10,
                value=3,
                key="tavily_uses",
                help="各商品に対してTAVILY APIを何回呼び出すか"
            )
        else:
            tavily_uses = 3

        sidebar_clear = st.button("クリア", use_container_width=True, help="候補とLLM出力を画面内でクリア")

        st.markdown("<div class='sidebar-bottom'>", unsafe_allow_html=True)
        if st.button("← 案件一覧に戻る", use_container_width=True):
            st.session_state.current_page = "案件一覧"
            st.session_state.page_changed = True
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    # ---------- タイトル ----------
    render_slide_generation_title(title_text)

    # ---------- 見出し行（左＝見出し / 右＝候補取得ボタン） ----------
    head_l, head_r = st.columns([8, 2])
    with head_l:
        st.subheader("1. 商品提案")
    with head_r:
        search_btn = st.button("候補を取得", use_container_width=True)

    # ====================== 1. 商品提案（左右2ペイン） ======================
    left, right = st.columns([5, 7], gap="large")

    # ---- 左：商談詳細 + 参考資料
    with left:
        st.markdown("**● 商談の詳細**")
        st.text_area(
            label="商談の詳細",
            key="slide_meeting_notes",
            height=160,
            label_visibility="collapsed",
            placeholder="例：来期の需要予測精度向上と在庫最適化。PoCから段階導入… など",
        )

        st.markdown("**● 参考資料**")
        uploads = st.file_uploader(
            label="参考資料（任意）",
            type=["pdf", "pptx", "docx", "csv", "png", "jpg", "jpeg"],
            accept_multiple_files=True,
            key="slide_uploader",
            label_visibility="collapsed",
            help="アップロード資料は特徴抽出/要約に利用する想定（現状はファイル名のみ文脈化）。",
        )
        if uploads:
            st.session_state.uploaded_files_store = uploads
            st.success(f"{len(uploads)} ファイルを受け付けました。")
        elif st.session_state.uploaded_files_store:
            st.caption(f"前回アップロード済み: {len(st.session_state.uploaded_files_store)} ファイル")

    # ---- 右：LLM提案（text_areaで枠内スクロール）
    with right:
        st.markdown("**● LLMによる提案**")

        # 「候補を取得」クリックで：候補検索 → LLM実行 → 出力保存
        if search_btn:
            if not company_internal.strip():
                st.error("企業が選択されていません。案件一覧から企業を選んでください。")
            else:
                with st.spinner("候補を検索中…"):
                    candidates = _search_product_candidates(
                        company=company_internal,
                        item_id=item_id,
                        meeting_notes=st.session_state.slide_meeting_notes or "",
                        top_k=int(st.session_state.slide_top_k),
                        history_n=int(st.session_state.slide_history_reference_count),
                        dataset=st.session_state.slide_products_dataset,
                        uploaded_files=st.session_state.uploaded_files_store,
                    )
                st.session_state.product_candidates = candidates

                with st.spinner("LLMで提案文を作成中…"):
                    st.session_state.llm_proposal_text = _run_llm_proposal(
                        company=company_internal,
                        meeting_notes=st.session_state.slide_meeting_notes or "",
                        item_id=item_id,
                        history_n=int(st.session_state.slide_history_reference_count),
                        candidates=candidates,
                        uploads=st.session_state.uploaded_files_store,
                        want=int(st.session_state.slide_top_k),
                    )

        if sidebar_clear:
            st.session_state.product_candidates = []
            st.session_state.llm_proposal_text = ""
            st.info("候補とLLM出力をクリアしました。")

        # ★ ここが確実に枠内に表示・スクロール
        st.text_area(
            label="LLM提案（表示専用）",
            value=st.session_state.llm_proposal_text or "候補を取得すると、ここにLLMの提案結果（要旨・推奨商材・次アクション）が表示されます。",
            height=370,                       # 左側の高さとバランスを合わせる
            key="llm_proposal_viewer",
            label_visibility="collapsed",
            disabled=True,                    # 読み取り専用
        )

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
            selected = list(st.session_state.product_candidates or [])
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
        
        # Добавляем кнопку генерации презентации
        st.markdown("---")
        st.subheader("3. プレゼンテーション生成")
        
        col1, col2 = st.columns([8, 2])
        with col1:
            st.info("下書きが作成されました。プレゼンテーションを生成するには下のボタンをクリックしてください。")
        with col2:
            generate_ppt_btn = st.button("プレゼンテーション生成", type="primary", use_container_width=True)
        
        if generate_ppt_btn:
            with st.spinner("AI Agentがプレゼンテーションを生成中..."):
                try:
                    # Получаем отчет о компании из сообщений
                    company_report = _get_company_report_from_messages(item_id)
                    
                    # Генерируем презентацию
                    pptx_bytes = slide_generator.generate_presentation(
                        company_name=company_internal,
                        company_report=company_report,
                        user_input=st.session_state.slide_meeting_notes or "",
                        llm_proposal=st.session_state.llm_proposal_text or "",
                        additional_instructions=st.session_state.slide_overview or "",
                        use_tavily_api=st.session_state.get("use_tavily_api", False),
                        use_gpt_api=st.session_state.get("use_gpt_api", False),
                        tavily_uses=st.session_state.get("tavily_uses", 3)
                    )
                    
                    # Предоставляем файл для скачивания
                    st.success("プレゼンテーションが生成されました！")
                    
                    filename = f"{company_internal}_提案資料_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pptx"
                    st.download_button(
                        label="📥 プレゼンテーションをダウンロード",
                        data=pptx_bytes,
                        file_name=filename,
                        mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                        use_container_width=True
                    )
                    
                except Exception as e:
                    st.error(f"プレゼンテーション生成でエラーが発生しました: {str(e)}")
                    st.exception(e)
