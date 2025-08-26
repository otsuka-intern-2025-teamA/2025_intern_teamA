# slide_generation_module.py
from __future__ import annotations

import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
from openai import AzureOpenAI, OpenAI

import streamlit as st

PROJECT_ROOT = Path(__file__).parent.parent.parent
LOGO_PATH = PROJECT_ROOT / "data" / "images" / "otsuka_logo.jpg"
ICON_PATH = PROJECT_ROOT / "data" / "images" / "otsuka_icon.png"
PRODUCTS_DIR = PROJECT_ROOT / "data" / "csv" / "products"
PLACEHOLDER_IMG = PROJECT_ROOT / "data" / "images" / "product_placeholder.png"

# --- スタイル / コンポーネント（既存の自作モジュールに合わせて）
from lib.api import api_available, get_api_client
from lib.slide_generator import SlideGenerator
from lib.styles import (
    apply_company_analysis_page_styles,
    apply_main_styles,
    apply_slide_generation_page_styles,
    apply_title_styles,
    render_sidebar_logo_card,
    render_slide_generation_title,
)


# =========================
# セッション初期化
# =========================
def _ensure_session_defaults() -> None:
    ss = st.session_state
    ss.setdefault("selected_project", None)
    ss.setdefault("api_error", None)
    ss.setdefault("slide_meeting_notes", "")
    ss.setdefault("uploaded_files_store", [])
    ss.setdefault("product_candidates", [])
    ss.setdefault("slide_outline", None)
    ss.setdefault("slide_overview", "")

    # ここが既定値（以降ウィジェットには value/index 渡さない）
    ss.setdefault("slide_history_reference_count", 3)  # 1〜10
    ss.setdefault("slide_top_k", 10)                   # 3〜20
    ss.setdefault("slide_products_dataset", "Auto")    # Auto or 実在フォルダ名
    ss.setdefault("slide_use_tavily_api", True)
    ss.setdefault("slide_use_gpt_api", True)
    ss.setdefault("slide_tavily_uses", 2)              # 1〜5


# =========================
# LLM クライアント準備
# =========================
def _get_chat_client():
    use_azure = os.getenv("USE_AZURE", "").lower() == "true" or bool(os.getenv("AZURE_OPENAI_ENDPOINT"))
    if use_azure:
        endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
        api_key = os.getenv("AZURE_OPENAI_API_KEY")
        api_version = os.getenv("API_VERSION", "2024-06-01")
        deployment = os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT")
        if not (endpoint and api_key and deployment):
            raise RuntimeError("Azure設定不足: AZURE_OPENAI_ENDPOINT / AZURE_OPENAI_API_KEY / AZURE_OPENAI_CHAT_DEPLOYMENT")
        client = AzureOpenAI(azure_endpoint=endpoint, api_key=api_key, api_version=api_version)
        model = deployment
    else:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY が未設定です。")
        client = OpenAI(api_key=api_key)
        model = os.getenv("DEFAULT_MODEL", "gpt-4o-mini")
    return client, model


def _to_float(val):
    if val is None:
        return None
    if isinstance(val, (int, float)):
        if isinstance(val, float) and pd.isna(val):
            return None
        return float(val)
    if isinstance(val, str):
        s = val.strip().replace("¥", "").replace(",", "")
        if not s:
            return None
        try:
            return float(s)
        except Exception:
            return None
    return None


def _fmt_price(val) -> str:
    v = _to_float(val)
    return f"¥{round(v):,}" if v is not None else "—"


def _list_product_datasets() -> list[str]:
    if not PRODUCTS_DIR.exists():
        return ["Auto"]
    ds = ["Auto"]
    for p in PRODUCTS_DIR.iterdir():
        if p.is_dir():
            ds.append(p.name)
    return ds


def _gather_messages_context(item_id: str | None, history_n: int) -> str:
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


def _load_products_from_csv(dataset: str) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    if not PRODUCTS_DIR.exists():
        return pd.DataFrame()

    def _read_csvs(folder: Path):
        for csvp in folder.glob("*.csv"):
            try:
                df = pd.read_csv(csvp)
                for col in ["name", "category", "price", "description", "tags"]:
                    if col not in df.columns:
                        df[col] = None
                for col in ["image_url", "image", "thumbnail"]:
                    if col not in df.columns:
                        df[col] = None
                if "id" not in df.columns:
                    df["id"] = [f"{csvp.stem}-{i+1}" for i in range(len(df))]
                df["source_csv"] = csvp.stem
                frames.append(df[["id", "name", "category", "price", "description", "tags",
                                  "image_url", "image", "thumbnail", "source_csv"]])
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


def _simple_tokenize(text: str) -> list[str]:
    text = str(text or "").lower()
    text = re.sub(r"[^a-z0-9\u3040-\u30ff\u4e00-\u9fff]+", " ", text)
    toks = text.split()
    return [t for t in toks if len(t) >= 2]


def _fallback_rank_products(notes: str, messages_ctx: str, products_df: pd.DataFrame, top_pool: int) -> list[dict[str, Any]]:
    if products_df.empty:
        return []
    query_text = (notes or "") + "\n" + (messages_ctx or "")
    q_tokens = _simple_tokenize(query_text)

    def _row_text(row) -> str:
        return " ".join([
            str(row.get("name") or ""),
            str(row.get("category") or ""),
            str(row.get("description") or ""),
            str(row.get("tags") or ""),
        ]).lower()

    scored: list[tuple[float, dict[str, Any]]] = []
    for _, row in products_df.iterrows():
        t = _row_text(row)
        score = sum(1.0 for tok in q_tokens if tok in t)
        reason = f"一致語句数={int(score)}" if score > 0 else "一致なし（低スコア）"
        scored.append((score, {
            "id": row.get("id"),
            "name": row.get("name"),
            "category": row.get("category"),
            "price": row.get("price"),
            "description": row.get("description"),
            "tags": row.get("tags"),
            "image_url": row.get("image_url"),
            "image": row.get("image"),
            "thumbnail": row.get("thumbnail"),
            "source_csv": row.get("source_csv"),
            "score": round(float(score), 2),
            "reason": reason,
        }))
    scored.sort(key=lambda x: (x[0], str(x[1]["name"]).lower()), reverse=True)
    return [d for _, d in scored[:top_pool]]


def _extract_json(s: str) -> dict[str, Any]:
    s = (s or "").strip()
    if not s:
        return {}
    if s.lstrip().startswith("{"):
        try:
            return json.loads(s)
        except Exception:
            pass
    try:
        start = s.find("{")
        end = s.rfind("}")
        if start >= 0 and end > start:
            return json.loads(s[start:end + 1])
    except Exception:
        return {}
    return {}


def _get_chat_json(client, model, messages):
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=messages,
            response_format={"type": "json_object"},
        )
        return resp.choices[0].message.content or ""
    except Exception:
        resp = client.chat.completions.create(model=model, messages=messages)
        return resp.choices[0].message.content or ""


def _llm_pick_products(pool: list[dict[str, Any]], top_k: int, company: str, notes: str, ctx: str) -> list[dict[str, Any]]:
    if not pool:
        return []
    client, model = _get_chat_client()

    lines = []
    for p in pool:
        desc = (p.get("description") or "")[:200]
        tags = (p.get("tags") or "")[:120]
        cat = p.get("source_csv") or p.get("category") or ""
        price = p.get("price")
        price_s = f"¥{int(_to_float(price)):,}" if _to_float(price) is not None else "—"
        lines.append(f"- id:{p['id']} | name:{p.get('name','')} | category:{cat} | price:{price_s} | tags:{tags} | desc:{desc}")
    catalog = "\n".join(lines)

    user = f"""あなたはB2Bプリセールスの提案プランナーです。
以下の会社情報と商談詳細、会話文脈に基づいて、候補カタログから Top-{top_k} の製品 id を選び、日本語で短い理由（120字以内）と信頼度(0-1)を付けてください。
必ずカタログに存在する id のみ。出力は JSON のみ:

{{
  "recommendations":[
    {{"id":"<id>","reason":"<120字以内>","confidence":0.0}}
  ]
}}

# 会社: {company}
# 商談詳細:
{notes or "(なし)"}

# 会話文脈:
{ctx or "(なし)"}

# 候補カタログ:
{catalog}
"""
    txt = _get_chat_json(
        client, model,
        [
            {"role": "system", "content": "あなたは正確で簡潔な日本語で回答するアシスタントです。"},
            {"role": "user", "content": user},
        ],
    )
    data = _extract_json(txt)
    recs = data.get("recommendations", []) if isinstance(data, dict) else []
    if not recs:
        return []

    pool_map = {str(p["id"]): p for p in pool}
    out: list[dict[str, Any]] = []
    for r in recs:
        pid = str(r.get("id", "")).strip()
        if not pid or pid not in pool_map:
            continue
        src = pool_map[pid]
        out.append({
            **src,
            "reason": (r.get("reason") or "").strip() or src.get("reason"),
            "score": float(r.get("confidence", 0.0)),
        })
        if len(out) >= top_k:
            break
    return out


def _summarize_overviews_llm(cands: list[dict[str, Any]]) -> None:
    items = []
    has_any = False
    for c in cands:
        mat = c.get("description") or c.get("tags") or c.get("name") or ""
        if mat:
            has_any = True
        items.append({"id": str(c.get("id") or ""), "name": c.get("name") or "", "material": str(mat)[:600]})

    if not has_any:
        for c in cands:
            c["overview"] = "—"
        return

    try:
        client, model = _get_chat_client()
        payload = "\n".join([f"- id:{it['id']} / 名称:{it['name']}\n  内容:{it['material']}" for it in items])
        prompt = f"""各製品の「製品概要」を日本語で1〜2文、最大80字で要約してください。事実の追加・誇張は禁止。
出力は JSON のみ:
{{"summaries":[{{"id":"<id>","overview":"<80字以内>"}}]}}
入力:
{payload}"""
        txt = _get_chat_json(
            client, model,
            [
                {"role": "system", "content": "あなたは簡潔で正確な日本語の要約を作るアシスタントです。"},
                {"role": "user", "content": prompt},
            ],
        )
        data = _extract_json(txt)
        mp = {}
        if isinstance(data, dict):
            for s in data.get("summaries", []) or []:
                pid = str(s.get("id") or "")
                ov = (s.get("overview") or "").strip()
                if pid and ov:
                    mp[pid] = ov

        for c in cands:
            pid = str(c.get("id") or "")
            base = c.get("description") or c.get("tags") or ""
            fallback = (base[:80] + ("…" if base and len(base) > 80 else "")) if base else "—"
            c["overview"] = mp.get(pid, fallback)
    except Exception:
        for c in cands:
            base = c.get("description") or c.get("tags") or ""
            c["overview"] = (base[:80] + ("…" if base and len(base) > 80 else "")) if base else "—"


def _resolve_product_image_src(rec: dict[str, Any]) -> str | None:
    for key in ("image_url", "image", "thumbnail"):
        v = rec.get(key)
        if not v:
            continue
        s = str(v).strip()
        if s.startswith("http://") or s.startswith("https://"):
            return s
        p = (PROJECT_ROOT / s).resolve()
        if p.exists():
            return str(p)
    if PLACEHOLDER_IMG.exists():
        return str(PLACEHOLDER_IMG)
    return None


def _search_product_candidates(
    company: str,
    item_id: str | None,
    meeting_notes: str,
    top_k: int,
    history_n: int,
    dataset: str,
    uploaded_files: list[Any],
) -> list[dict[str, Any]]:
    ctx = _gather_messages_context(item_id, history_n)

    df = _load_products_from_csv(dataset)
    if df.empty:
        return []

    pool = _fallback_rank_products(meeting_notes, ctx, df, top_pool=max(40, top_k * 3))

    try:
        selected = _llm_pick_products(pool, top_k, company, meeting_notes, ctx)
        if not selected:
            selected = pool[:top_k]
    except Exception:
        selected = pool[:top_k]

    _summarize_overviews_llm(selected)
    return selected


def _make_outline_preview(company: str, meeting_notes: str, selected_products: list[dict[str, Any]], overview: str) -> dict[str, Any]:
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
            {
                "id": p.get("id"),
                "name": p.get("name"),
                "category": p.get("source_csv") or p.get("category"),
                "price": p.get("price"),
                "reason": p.get("reason"),
                "overview": p.get("overview"),
            }
            for p in selected_products
        ],
    }


def render_slide_generation_page():
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

    apply_main_styles(hide_sidebar=False, hide_header=True)
    apply_title_styles()
    apply_company_analysis_page_styles()
    apply_slide_generation_page_styles()

    pj = st.session_state.get("selected_project")
    if pj:
        title_text = f"スライド作成 - {pj['title']} / {pj['company']}"
        company_internal = pj.get("company", "")
        item_id = pj.get("id")
    else:
        title_text = "スライド作成"
        company_internal = ""
        item_id = None

    with st.sidebar:
        render_sidebar_logo_card(LOGO_PATH)
        st.markdown("### 設定")
        st.text_input("企業名", value=company_internal, key="slide_company_input", disabled=True)

        # --- ここから“数字はすべて一覧選択型” & Session State 既定値のみ使用 ---
        st.selectbox("提案件数", options=list(range(3, 21)), key="slide_top_k")

        st.selectbox(
            "履歴参照件数（往復）",
            options=list(range(1, 11)),
            key="slide_history_reference_count",
            help="企業分析のチャット履歴の直近N往復を文脈として使用",
        )

        st.selectbox(
            "商材データセット",
            options=_list_product_datasets(),
            key="slide_products_dataset",
            help="data/csv/products/ 配下のフォルダ。Autoは自動選択。",
        )

        st.markdown("---")
        st.markdown("### AI設定")

        st.checkbox("GPT API使用", key="slide_use_gpt_api")
        st.checkbox("TAVILY API使用", key="slide_use_tavily_api")

        if st.session_state.slide_use_tavily_api:
            st.selectbox("TAVILY API呼び出し回数（製品あたり）", options=list(range(1, 6)), key="slide_tavily_uses")

        sidebar_clear = st.button("クリア", use_container_width=True)

        st.markdown("<div class='sidebar-bottom'>", unsafe_allow_html=True)
        if st.button("← 案件一覧に戻る", use_container_width=True):
            st.session_state.current_page = "案件一覧"
            st.session_state.page_changed = True
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    render_slide_generation_title(title_text)

    head_l, head_r = st.columns([8, 2])
    with head_l:
        st.subheader("1. 商品提案")
    with head_r:
        search_btn = st.button("候補を取得", use_container_width=True)

    left, right = st.columns([5, 7], gap="large")

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

    with right:
        st.markdown("**● 候補（カード表示）**")

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

        if sidebar_clear:
            st.session_state.product_candidates = []
            st.info("候補をクリアしました。")

        recs = st.session_state.product_candidates or []
        if not recs:
            st.info("候補がありません。『候補を取得』を押してください。")
        else:
            for r in recs:
                pid = str(r.get("id") or "")
                name = str(r.get("name") or "")
                cat_src = r.get("source_csv") or r.get("category") or "—"
                price_s = _fmt_price(r.get("price"))
                reason = r.get("reason") or "—"
                overview = r.get("overview") or "—"

                with st.container(border=True):
                    c1, c2 = st.columns([1, 3], gap="medium")
                    with c1:
                        img_src = _resolve_product_image_src(r)
                        if img_src and (img_src.startswith("http") or os.path.exists(img_src)):
                            st.image(img_src, use_container_width=True)
                        else:
                            st.markdown(
                                "<div style='width:100%;height:120px;border:1px solid #eee;border-radius:10px;"
                                "background:#f6f7f9;display:flex;align-items:center;justify-content:center;"
                                "color:#999;font-size:12px;'>画像なし</div>",
                                unsafe_allow_html=True
                            )
                    with c2:
                        st.markdown(f"**{name}**")
                        st.caption(f"カテゴリ: {cat_src} ／ 価格: {price_s} ／ ID: `{pid}`")
                        st.markdown(f"**提案理由**：{reason}")
                        st.markdown(f"**製品概要**：{overview}")

    st.divider()

    st.subheader("2. スライド生成")
    row_l, row_r = st.columns([8, 2], vertical_alignment="center")
    with row_l:
        # これは key を使わず戻り値を直接 Session State に入れるので OK
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
        elif not st.session_state.product_candidates:
            st.error("製品候補がありません。先に「候補を取得」を押してください。")
        else:
            selected = list(st.session_state.product_candidates or [])
            outline = _make_outline_preview(
                company_internal,
                st.session_state.slide_meeting_notes or "",
                selected,
                st.session_state.slide_overview or "",
            )
            st.session_state.slide_outline = outline

            with st.spinner("AIエージェントがプレゼンテーションを生成中..."):
                try:
                    generator = SlideGenerator()
                    pptx_data = generator.create_presentation(
                        company_name=company_internal,
                        meeting_notes=st.session_state.slide_meeting_notes or "",
                        products=selected,
                        use_tavily=st.session_state.slide_use_tavily_api,
                        use_gpt=st.session_state.slide_use_gpt_api,
                        tavily_uses=st.session_state.slide_tavily_uses
                    )
                    st.success("プレゼンテーションが生成されました！")
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    filename = f"{company_internal}_提案書_{timestamp}.pptx"
                    st.download_button(
                        label="📥 プレゼンテーションをダウンロード",
                        data=pptx_data,
                        file_name=filename,
                        mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                        use_container_width=True,
                        type="primary"
                    )
                except Exception as e:
                    st.error(f"プレゼンテーション生成でエラーが発生しました: {e}")
                    st.info("下書きのみ作成されました。")

    if st.session_state.slide_outline:
        with st.expander("下書きプレビュー（JSON）", expanded=True):
            st.json(st.session_state.slide_outline)
