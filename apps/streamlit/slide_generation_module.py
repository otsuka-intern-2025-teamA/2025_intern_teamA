# slide_generation_module.py
# ---------------------------------------------------------
# スライド作成ページ（カードUI）
# - 候補は：
#   1) CSVから粗選定（語句一致）
#   2) LLMで Top-K 選抜＋提案理由を生成（失敗時はフォールバック理由）
#   3) LLMで製品概要(<=80字)を要約（失敗時は短縮表示）
# ---------------------------------------------------------

from __future__ import annotations
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import os, re, json
import streamlit as st
import pandas as pd

from lib.styles import apply_main_styles, apply_scroll_script
from lib.api import get_api_client, api_available, APIError

# LLM クライアント（このファイル内で環境変数から作る）
from openai import OpenAI, AzureOpenAI

PROJECT_ROOT = Path(__file__).parent.parent.parent
LOGO_PATH = PROJECT_ROOT / "data" / "images" / "otsuka_logo.jpg"
ICON_PATH = PROJECT_ROOT / "data" / "images" / "otsuka_icon.png"
PRODUCTS_DIR = PROJECT_ROOT / "data" / "csv" / "products"
PLACEHOLDER_IMG = PROJECT_ROOT / "data" / "images" / "product_placeholder.png"

# ====== 基本ユーティリティ ======
def _to_float(val):
    if val is None:
        return None
    if isinstance(val, (int, float)):
        if isinstance(val, float) and pd.isna(val):
            return None
        return float(val)
    if isinstance(val, str):
        s = val.strip().replace("¥", "").replace(",", "")
        if s == "":
            return None
        try:
            return float(s)
        except Exception:
            return None
    return None

def _fmt_price(val) -> str:
    v = _to_float(val)
    return f"¥{int(round(v)):,}" if v is not None else "—"

# ====== セッション初期化 ======
def _ensure_session_defaults() -> None:
    ss = st.session_state
    ss.setdefault("selected_project", None)
    ss.setdefault("api_error", None)
    ss.setdefault("slide_meeting_notes", "")
    ss.setdefault("uploaded_files_store", [])
    ss.setdefault("product_candidates", [])        # dict list: id,name,source_csv,price,reason,overview...
    ss.setdefault("slide_outline", None)
    ss.setdefault("slide_overview", "")
    ss.setdefault("slide_history_reference_count", 3)
    ss.setdefault("slide_top_k", 10)
    ss.setdefault("slide_products_dataset", "Auto")

# ====== 環境変数から LLM クライアントを用意 ======
def _get_chat_client():
    """
    Azure or OpenAI を自動選択。
    - Azure: USE_AZURE=true または AZURE_OPENAI_ENDPOINT があれば
      必要: AZURE_OPENAI_API_KEY, AZURE_OPENAI_CHAT_DEPLOYMENT
      任意: API_VERSION (default 2024-06-01)
    - OpenAI: OPENAI_API_KEY, DEFAULT_MODEL(optional, default gpt-4o-mini)
    戻り: (client, model_or_deployment)
    """
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

# ====== データセット読込（CSV名をカテゴリ表示に使う） ======
def _list_product_datasets() -> List[str]:
    if not PRODUCTS_DIR.exists():
        return ["Auto"]
    out = ["Auto"]
    for p in PRODUCTS_DIR.iterdir():
        if p.is_dir():
            out.append(p.name)
    return out

def _load_products_from_csv(dataset: str) -> pd.DataFrame:
    frames: List[pd.DataFrame] = []
    if not PRODUCTS_DIR.exists():
        return pd.DataFrame()

    def _read_csvs(folder: Path):
        for csvp in folder.glob("*.csv"):
            try:
                df = pd.read_csv(csvp)
                for col in ["name","category","price","description","tags"]:
                    if col not in df.columns: df[col] = None
                for col in ["image_url","image","thumbnail"]:
                    if col not in df.columns: df[col] = None
                if "id" not in df.columns:
                    df["id"] = [f"{csvp.stem}-{i+1}" for i in range(len(df))]
                df["source_csv"] = csvp.stem  # ← CSVファイル名
                frames.append(df[["id","name","category","price","description","tags","image_url","image","thumbnail","source_csv"]])
            except Exception:
                continue

    if dataset == "Auto":
        for sub in PRODUCTS_DIR.iterdir():
            if sub.is_dir():
                _read_csvs(sub)
        _read_csvs(PRODUCTS_DIR)
    else:
        tgt = PRODUCTS_DIR / dataset
        if tgt.exists() and tgt.is_dir():
            _read_csvs(tgt)

    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)

# ====== 企業分析チャット履歴の要約取り出し（文脈） ======
def _gather_messages_context(item_id: Optional[str], history_n: int) -> str:
    if not (item_id and api_available()):
        return ""
    try:
        api = get_api_client()
        msgs = api.get_item_messages(item_id) or []
        take = min(len(msgs), history_n * 2)
        recent = msgs[-take:] if take > 0 else []
        lines = []
        for m in recent:
            role = m.get("role","assistant")
            who = "ユーザー" if role == "user" else "アシスタント"
            lines.append(f"{who}:{m.get('content','')}")
        return "\n".join(lines)
    except Exception:
        return ""

# ====== 粗選定（語句一致の素朴スコア） ======
_nonword = re.compile(r"[^a-z0-9\u3040-\u30ff\u4e00-\u9fff]+", re.IGNORECASE)
def _simple_tokenize(text: str) -> List[str]:
    t = str(text or "")
    t = _nonword.sub(" ", t.lower())
    return [x for x in t.split() if len(x) >= 2]

def _fallback_rank_products(notes: str, messages_ctx: str, df: pd.DataFrame, top_pool: int) -> List[Dict[str, Any]]:
    if df.empty: return []
    q = (notes or "") + "\n" + (messages_ctx or "")
    q_toks = _simple_tokenize(q)

    def row_text(r) -> str:
        return " ".join([str(r.get("name") or ""),
                         str(r.get("category") or ""),
                         str(r.get("description") or ""),
                         str(r.get("tags") or "")]).lower()

    scored: List[Tuple[float, Dict[str, Any]]] = []
    for _, r in df.iterrows():
        text = row_text(r)
        score = sum(1.0 for t in q_toks if t in text) if q_toks else 0.0
        out = {
            "id": r.get("id"),
            "name": r.get("name"),
            "category": r.get("category"),
            "price": r.get("price"),
            "description": r.get("description"),
            "tags": r.get("tags"),
            "image_url": r.get("image_url"),
            "image": r.get("image"),
            "thumbnail": r.get("thumbnail"),
            "source_csv": r.get("source_csv"),
            "score": float(score),
            "reason": "一致なし（低スコア）" if score <= 0 else f"一致語句数={int(score)}",
        }
        scored.append((score, out))
    scored.sort(key=lambda x: (x[0], str(x[1]["name"]).lower()), reverse=True)
    return [d for _, d in scored[:top_pool]]

# ====== JSON抽出（前後に文章が付いても拾う） ======
def _extract_json(s: str) -> Dict[str, Any]:
    s = (s or "").strip()
    if not s: return {}
    if s.lstrip().startswith("{"):
        try: return json.loads(s)
        except Exception: pass
    # 最後の } までを拾う
    try:
        start = s.find("{")
        end = s.rfind("}")
        if start >= 0 and end > start:
            return json.loads(s[start:end+1])
    except Exception:
        return {}
    return {}

# ====== LLMで Top-K を選抜＋理由生成 ======
def _llm_pick_products(pool: List[Dict[str, Any]], top_k: int, company: str, notes: str, ctx: str) -> List[Dict[str, Any]]:
    if not pool: return []
    client, model = _get_chat_client()

    # カタログ（過度なトークンを避けるため description/tags は短く）
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
    try:
        # JSONモード対応
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role":"system","content":"あなたは正確で簡潔な日本語で回答するアシスタントです。"},
                      {"role":"user","content":user}],
            response_format={"type":"json_object"},
        )
        txt = resp.choices[0].message.content or ""
    except Exception:
        # 非JSONモード
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role":"system","content":"あなたは正確で簡潔な日本語で回答するアシスタントです。"},
                      {"role":"user","content":user}],
        )
        txt = resp.choices[0].message.content or ""

    data = _extract_json(txt)
    recs = data.get("recommendations", []) if isinstance(data, dict) else []
    if not recs:
        return []

    # id マップ
    pool_map = {str(p["id"]): p for p in pool}
    out: List[Dict[str, Any]] = []
    for r in recs:
        pid = str(r.get("id","")).strip()
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

# ====== 製品概要を LLM で要約（<=80字） ======
def _summarize_overviews_llm(cands: List[Dict[str, Any]]) -> bool:
    # 素材作成
    items = []
    has_any = False
    for c in cands:
        mat = c.get("description") or c.get("tags") or c.get("name") or ""
        if mat: has_any = True
        items.append({"id": str(c.get("id") or ""), "name": c.get("name") or "", "material": str(mat)[:600]})
    if not has_any:
        for c in cands:
            c["overview"] = "—"
        return False

    try:
        client, model = _get_chat_client()
        payload = "\n".join([f"- id:{it['id']} / 名称:{it['name']}\n  内容:{it['material']}" for it in items])
        prompt = f"""各製品の「製品概要」を日本語で1〜2文、最大80字で要約してください。事実の追加・誇張は禁止。
出力は JSON のみ:
{{"summaries":[{{"id":"<id>","overview":"<80字以内>"}}]}}
入力:
{payload}"""
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[{"role":"system","content":"あなたは簡潔で正確な日本語の要約を作るアシスタントです。"},
                          {"role":"user","content":prompt}],
                response_format={"type":"json_object"},
            )
            txt = resp.choices[0].message.content or ""
        except Exception:
            resp = client.chat.completions.create(
                model=model,
                messages=[{"role":"system","content":"あなたは簡潔で正確な日本語の要約を作るアシスタントです。"},
                          {"role":"user","content":prompt}],
            )
            txt = resp.choices[0].message.content or ""

        data = _extract_json(txt)
        m = {}
        if isinstance(data, dict):
            for s in data.get("summaries", []) or []:
                pid = str(s.get("id") or "")
                ov = (s.get("overview") or "").strip()
                if pid and ov:
                    m[pid] = ov

        for c in cands:
            pid = str(c.get("id") or "")
            base = c.get("description") or c.get("tags") or ""
            fallback = (base[:80] + ("…" if base and len(base) > 80 else "")) if base else "—"
            c["overview"] = m.get(pid, fallback)
        return True
    except Exception:
        for c in cands:
            base = c.get("description") or c.get("tags") or ""
            c["overview"] = (base[:80] + ("…" if base and len(base) > 80 else "")) if base else "—"
        return False

# ====== 画像パス解決 ======
def _resolve_product_image_src(rec: Dict[str, Any]) -> Optional[str]:
    for key in ("image_url","image","thumbnail"):
        v = rec.get(key)
        if not v: continue
        s = str(v).strip()
        if s.startswith("http://") or s.startswith("https://"):
            return s
        p = (PROJECT_ROOT / s).resolve()
        if p.exists(): return str(p)
    if PLACEHOLDER_IMG.exists(): return str(PLACEHOLDER_IMG)
    return None

# ====== 下書き構成 ======
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
            {"id": p.get("id"), "name": p.get("name"),
             "category": p.get("source_csv") or p.get("category"),
             "price": p.get("price"), "reason": p.get("reason"),
             "overview": p.get("overview")}
            for p in selected_products
        ],
    }

# ====== 候補取得（LLM選抜＋フォールバック） ======
def _search_product_candidates(company: str, item_id: Optional[str], meeting_notes: str, top_k: int, history_n: int, dataset: str, uploaded_files: List[Any]) -> Tuple[List[Dict[str, Any]], List[Tuple[str,str]]]:
    notices: List[Tuple[str,str]] = []
    # 企業分析の文脈
    ctx = _gather_messages_context(item_id, history_n)

    # カタログ読み込み
    df = _load_products_from_csv(dataset)
    if df.empty:
        return [], [("warning","商材CSVが見つかりません。")]

    # まず粗選定（Top-40）
    pool = _fallback_rank_products(meeting_notes, ctx, df, top_pool=max(40, top_k*3))

    # LLMで Top-K を選抜＋理由生成
    selected: List[Dict[str,Any]] = []
    try:
        selected = _llm_pick_products(pool, top_k, company, meeting_notes, ctx)
        if not selected:
            notices.append(("info","LLMが選抜できなかったため、粗選定の上位を採用します。"))
            selected = pool[:top_k]
        else:
            notices.append(("success", f"LLMで {len(selected)} 件を選抜しました。"))
    except Exception as e:
        notices.append(("error", f"LLM選抜に失敗: {e}"))
        selected = pool[:top_k]

    # 製品概要を LLM で要約（<=80字）。失敗時は短縮表示。
    used_llm = _summarize_overviews_llm(selected)
    if used_llm:
        notices.append(("info", "製品概要は LLM で要約しました。"))
    else:
        notices.append(("info", "製品概要は CSV の説明を短縮表示しています（LLM未使用/失敗）。"))

    return selected, notices

# ====== 画面描画 ======
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
            item_id = pj.get("id")
        else:
            st.title("スライド作成")
            company_internal = ""
            item_id = None
    with header_col2:
        st.markdown("")
        try:
            st.image(str(LOGO_PATH), width=160, use_container_width=False)
        except Exception:
            pass

    if st.button("← 案件一覧に戻る"):
        st.session_state.current_page = "案件一覧"
        st.session_state.page_changed = True
        st.rerun()

    # 1. 商品提案
    st.subheader("1. 商品提案")
    left, right = st.columns([5, 7], gap="large")
    notices: List[Tuple[str, str]] = []

    with left:
        st.text_area(
            "商談の詳細",
            key="slide_meeting_notes",
            height=160,
            placeholder="例：来期の需要予測精度向上と在庫最適化。PoCから段階導入… など",
        )
        uploads = st.file_uploader(
            "参考資料（任意）",
            type=["pdf","pptx","docx","xlsx","csv","png","jpg","jpeg","txt","md"],
            accept_multiple_files=True,
            key="slide_uploader",
        )
        if uploads:
            st.session_state.uploaded_files_store = uploads
            st.success(f"{len(uploads)} ファイルを受け付けました。")
        elif st.session_state.uploaded_files_store:
            st.caption(f"前回アップロード済み: {len(st.session_state.uploaded_files_store)} ファイル")

        # 提案件数 & データセット & 取得ボタン（横並び）
        b1, b2, b3, b4 = st.columns([0.9, 0.9, 2.0, 1.6], vertical_alignment="center")
        with b1:
            st.markdown("**提案件数**")
        with b2:
            st.number_input("", min_value=3, max_value=20, step=1, key="slide_top_k", label_visibility="collapsed")
        with b3:
            datasets = _list_product_datasets()
            st.session_state.slide_products_dataset = st.selectbox(
                "データセット",
                options=datasets,
                index=datasets.index(st.session_state.slide_products_dataset) if st.session_state.slide_products_dataset in datasets else 0,
            )
        with b4:
            search_btn = st.button("候補を取得", use_container_width=True)

    if search_btn:
        if not company_internal.strip():
            notices.append(("error", "企業が選択されていません。案件一覧から企業を選んでください。"))
        else:
            with st.spinner("候補を検索中…"):
                cands, n2 = _search_product_candidates(
                    company=company_internal,
                    item_id=item_id,
                    meeting_notes=st.session_state.slide_meeting_notes or "",
                    top_k=int(st.session_state.slide_top_k),
                    history_n=int(st.session_state.slide_history_reference_count),
                    dataset=st.session_state.slide_products_dataset,
                    uploaded_files=st.session_state.uploaded_files_store,
                )
            st.session_state.product_candidates = cands
            notices.extend(n2)

    # 右：カード表示（選択機能なし）
    with right:
        st.markdown("候補（カード）")
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

    # 通知
    if notices:
        for level, msg in notices:
            {"success": st.success, "info": st.info, "warning": st.warning, "error": st.error}.get(level, st.write)(msg)

    st.divider()

    # 2. スライド生成
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
            recs = st.session_state.product_candidates or []
            selected = list(recs)  # 選択機能なし：全候補を採用
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
