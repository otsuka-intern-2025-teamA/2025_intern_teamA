# slide_generation_module.py
# ---------------------------------------------------------
# スライド作成ページ（サイドバー追加版 × カードUI）
# - サイドバー：ロゴ／案件一覧へ戻る（左下固定）／企業名／提案件数／履歴参照件数／商材データセット選択／クリア
# - 本文：上段ヘッダ（左＝見出し／右＝候補取得ボタン）、
#          1段目＝商談詳細（大）＆参考資料（横並び）、
#          2段目＝左：課題分析（自動）／右：候補カード
#          下段＝生成とドラフトJSON
# - 生成ロジック：CSV→粗選定→LLMでTop-K選抜→LLMで80字要約（失敗時は短縮）
# ---------------------------------------------------------

from __future__ import annotations
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import os, re, json
from datetime import datetime

import streamlit as st
import pandas as pd
import numpy as np

# 共通スタイル
from lib.styles import (
    apply_main_styles,
    apply_title_styles,
    apply_company_analysis_page_styles,   # サイドバー圧縮/ロゴカード/下寄せCSSを流用
    apply_slide_generation_page_styles,
    render_sidebar_logo_card,
    render_slide_generation_title,        # タイトル描画（h1.slide-generation-title）
)

# APIクライアント（企業分析のチャット履歴取得に使用）
from lib.api import get_api_client, api_available, APIError

# スライド生成モジュール
from lib.slide_generator import SlideGenerator

# LLM クライアント（Azure / OpenAI どちらでもOK）
from openai import OpenAI, AzureOpenAI

# 画像/データパス
PROJECT_ROOT = Path(__file__).parent.parent.parent
LOGO_PATH = PROJECT_ROOT / "data" / "images" / "otsuka_logo.jpg"
ICON_PATH = PROJECT_ROOT / "data" / "images" / "otsuka_icon.png"
PRODUCTS_DIR = PROJECT_ROOT / "data" / "csv" / "products"
PLACEHOLDER_IMG = PROJECT_ROOT / "data" / "images" / "product_placeholder.png"

# --- スタイル / コンポーネント（既存の自作モジュールに合わせて）
from lib.api import api_available, get_api_client
from lib.new_slide_generator import NewSlideGenerator
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
    ss.setdefault("selected_project", None)       # 案件一覧から遷移時に入る
    ss.setdefault("api_error", None)
    ss.setdefault("slide_meeting_notes", "")
    ss.setdefault("uploaded_files_store", [])     # file_uploaderの保存用
    ss.setdefault("product_candidates", [])       # 表示用カードデータの配列
    ss.setdefault("slide_outline", None)
    ss.setdefault("slide_overview", "")
    ss.setdefault("slide_history_reference_count", 3)  # 直近N往復参照（デフォ3）
    ss.setdefault("slide_top_k", 10)                   # 提案件数（デフォ10）
    ss.setdefault("slide_products_dataset", "Auto")    # 商材データセット選択
    ss.setdefault("slide_use_tavily_api", True)        # TAVILY API使用フラグ
    ss.setdefault("slide_use_gpt_api", True)           # GPT API使用フラグ
    ss.setdefault("slide_tavily_uses", 2)              # 製品あたりのTAVILY API呼び出し回数
    # 埋め込み検索用キャッシュ
    ss.setdefault("_emb_cache", {})
    # 表示用：課題分析結果（UIで見せるだけ。選定ロジックは従来通り）
    ss.setdefault("analyzed_issues", [])


# =========================
# LLM クライアント準備（Azure / OpenAI 自動判定）
# =========================
def _get_chat_client():
    """
    - Azure: USE_AZURE=true or AZURE_OPENAI_ENDPOINT があれば使用
      必須: AZURE_OPENAI_API_KEY, AZURE_OPENAI_CHAT_DEPLOYMENT
      任意: API_VERSION (default 2024-06-01)
    - OpenAI: OPENAI_API_KEY, DEFAULT_MODEL (任意・既定 gpt-4o-mini)
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


# =========================
# 便利関数（価格など）
# =========================
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
    return f"¥{int(round(v)):,}" if v is not None else "—"


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


def _load_products_from_csv(dataset: str) -> pd.DataFrame:
    """
    商材CSVをロード（存在カラムが無ければ作成）
    期待カラム: id(無ければ生成), name, category, price, description, tags
             ＋ image_url/image/thumbnail（任意）, source_csv（追加）
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


# =========================
# 参考資料（アップロードファイル）テキスト抽出【追加】
# =========================
def _extract_text_from_uploads(uploaded_files: List[Any], max_chars: int = 12000) -> str:
    """
    アップロード資料からテキストを抽出して連結して返す（ロバストに動く簡易実装）。
    - PDF: pypdf
    - DOCX: python-docx
    - PPTX: python-pptx
    - CSV: pandasで先頭数行
    - TXT: そのまま
    失敗時はファイル名の記録のみ。画像/OCRは未対応。
    """
    if not uploaded_files:
        return ""

    chunks: List[str] = []
    used_chars = 0

    def _append(text: str):
        nonlocal used_chars
        if not text:
            return
        remain = max_chars - used_chars
        if remain <= 0:
            return
        cut = text[:remain]
        chunks.append(cut)
        used_chars += len(cut)

    for f in uploaded_files:
        try:
            name = getattr(f, "name", "uploaded_file")
            lower = str(name).lower()
            # 読み出し位置を初期化
            try:
                f.seek(0)
            except Exception:
                pass
            data = f.read()
            try:
                f.seek(0)
            except Exception:
                pass

            if lower.endswith(".pdf"):
                try:
                    from pypdf import PdfReader  # pip install pypdf
                    import io
                    reader = PdfReader(io.BytesIO(data))
                    page_limit = min(len(reader.pages), 30)
                    texts = []
                    for i in range(page_limit):
                        try:
                            texts.append(reader.pages[i].extract_text() or "")
                        except Exception:
                            continue
                    _append(f"\n[PDF:{name} 抜粋]\n" + "\n".join(texts))
                except Exception:
                    _append(f"\n[PDF:{name}]（抽出失敗→ファイル名のみ反映）")

            elif lower.endswith(".docx"):
                try:
                    import io
                    from docx import Document  # pip install python-docx
                    doc = Document(io.BytesIO(data))
                    paras = [p.text for p in doc.paragraphs if p.text]
                    _append(f"\n[DOCX:{name} 抜粋]\n" + "\n".join(paras))
                except Exception:
                    _append(f"\n[DOCX:{name}]（抽出失敗→ファイル名のみ反映）")

            elif lower.endswith(".pptx"):
                try:
                    import io
                    from pptx import Presentation  # pip install python-pptx
                    prs = Presentation(io.BytesIO(data))
                    slide_texts = []
                    for s in prs.slides:
                        buf = []
                        for shp in s.shapes:
                            try:
                                if hasattr(shp, "text"):
                                    t = shp.text or ""
                                    if t:
                                        buf.append(t)
                            except Exception:
                                continue
                        if buf:
                            slide_texts.append("\n".join(buf))
                    _append(f"\n[PPTX:{name} 抜粋]\n" + "\n---\n".join(slide_texts))
                except Exception:
                    _append(f"\n[PPTX:{name}]（抽出失敗→ファイル名のみ反映）")

            elif lower.endswith(".csv"):
                try:
                    import io
                    tmp = io.BytesIO(data)
                    df = pd.read_csv(tmp)
                    head = df.head(20)
                    txt = head.to_csv(index=False)
                    _append(f"\n[CSV:{name} 先頭20行]\n{txt}")
                except Exception:
                    _append(f"\n[CSV:{name}]（抽出失敗→ファイル名のみ反映）")

            elif lower.endswith(".txt"):
                try:
                    txt = data.decode("utf-8", errors="ignore")
                except Exception:
                    txt = str(data[:4000])
                _append(f"\n[TXT:{name}]\n{txt}")

            else:
                _append(f"\n[{name}]（未対応/バイナリのため概要反映のみ）")

        except Exception:
            continue

        if used_chars >= max_chars:
            break

    return "\n".join(chunks).strip()


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
    top_pool: int
) -> List[Dict[str, Any]]:
    """商談メモ＋履歴の語句一致で素朴にスコアリング → 上位 top_pool を返す"""
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


# =========================
# LLM で Top-K 選抜＋理由生成 / 80字要約
# =========================
def _extract_json(s: str) -> Dict[str, Any]:
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


def _llm_pick_products(pool: List[Dict[str, Any]], top_k: int, company: str, notes: str, ctx: str, issues: Optional[List[Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
    """
    カタログ（pool）から LLM で Top-K を選抜し、短い理由と信頼度を付与。
    issues が与えられれば、課題IDとの対応付けと根拠を求める。
    """
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
    # 課題リストを文字列化
    issues_text = ""
    if issues:
        parts = []
        for i, it in enumerate(issues):
            kw = ", ".join(it.get("keywords") or [])
            parts.append(f"[{i}] {it.get('issue')} (重み={it.get('weight'):.2f}; キーワード={kw})")
        issues_text = "\n".join(parts)
    # JSONスキーマ
    schema = {
        "recommendations": [
            {
                "id": "<id>",
                "reason": "<120字以内>",
                "confidence": 0.0,
            }
        ]
    }
    if issues:
        schema = {
            "recommendations": [
                {
                    "id": "<id>",
                    "reason": "<120字以内>",
                    "confidence": 0.0,
                    "solved_issue_ids": [0],
                    "evidence": "<根拠抜粋>"
                }
            ]
        }
    user = f"""あなたはB2Bプリセールスの提案プランナーです。
以下の会社情報と商談詳細、会話文脈に基づいて、候補カタログから Top-{top_k} の製品を選び、日本語で短い理由（120字以内）と信頼度(0-1)を付けてください。
必ずカタログに存在する id のみを使用してください。
出力は JSON のみで、以下のスキーマに従ってください:
{json.dumps(schema, ensure_ascii=False)}

# 会社: {company or "(なし)"}
# 商談詳細:
{notes or "(なし)"}

# 会話文脈:
{ctx or "(なし)"}

# 課題一覧:
{issues_text or "(なし)"}

# 候補カタログ:
{catalog}
"""
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "あなたは正確で簡潔な日本語で回答するアシスタントです。"},
                {"role": "user", "content": user},
            ],
            response_format={"type": "json_object"},
        )
        txt = resp.choices[0].message.content or ""
    except Exception:
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "あなたは正確で簡潔な日本語で回答するアシスタントです。"},
                {"role": "user", "content": user},
            ],
        )
        txt = resp.choices[0].message.content or ""

    data = _extract_json(txt)
    recs = data.get("recommendations", []) if isinstance(data, dict) else []
    if not recs:
        return []
    pool_map = {str(p["id"]): p for p in pool}
    out: List[Dict[str, Any]] = []
    for r in recs:
        pid = str(r.get("id", "")).strip()
        if not pid or pid not in pool_map:
            continue
        src = pool_map[pid]
        # reason / confidence
        reason = (r.get("reason") or "").strip() or src.get("reason")
        conf = float(r.get("confidence", 0.0)) if r.get("confidence") is not None else float(src.get("score", 0.0))
        solved_ids = r.get("solved_issue_ids") if isinstance(r.get("solved_issue_ids"), list) else []
        evidence = (r.get("evidence") or "").strip()
        out.append({
            **src,
            "reason": reason,
            "score": conf,
            "solved_issue_ids": solved_ids,
            "evidence": evidence,
        })
        if len(out) >= top_k:
            break
    return out


def _summarize_overviews_llm(cands: List[Dict[str, Any]]) -> None:
    """各製品の概要を 80字以内で LLM 要約（失敗時は説明を短縮）"""
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
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "あなたは簡潔で正確な日本語の要約を作るアシスタントです。"},
                    {"role": "user", "content": prompt},
                ],
                response_format={"type": "json_object"},
            )
            txt = resp.choices[0].message.content or ""
        except Exception:
            resp = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "あなたは簡潔で正確な日本語の要約を作るアシスタントです。"},
                    {"role": "user", "content": prompt},
                ],
            )
            txt = resp.choices[0].message.content or ""

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


def _resolve_product_image_src(rec: Dict[str, Any]) -> Optional[str]:
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

# =========================
# 追加: 課題分析・埋め込み索引・類似検索
# =========================

def _analyze_pain_points(notes: str, messages_ctx: str, uploads_text: str = "") -> List[Dict[str, Any]]:
    """
    商談メモ・会話文脈・アップロード資料（抽出テキスト）から課題を抽出。
    返り値: [{"issue": str, "weight": float, "keywords": List[str]}, ...]
    フォールバック時は汎用的な課題を返す。
    """
    issues: List[Dict[str, Any]] = []
    try:
        client, chat_model = _get_chat_client()
        sys = "あなたはB2B提案の課題分析アシスタントです。日本語でJSONのみ出力してください。"

        uploads_section = f"\n\n資料抜粋:\n{uploads_text}" if uploads_text else ""

        user = f"""以下の情報から、解決したい課題を3〜6件抽出し、各課題に重み(0〜1)と関連キーワード(3〜6語)を付けてJSONで出力してください。
- 課題は具体的に表現する
- 重みは合計が約1になるよう相対調整
- 引用可能なら資料由来の観点も反映（ただし機密や個人情報は抽象化）

商談メモ:
{notes}

会話文脈:
{messages_ctx}{uploads_section}
"""
        resp = client.chat.completions.create(
            model=chat_model,
            messages=[
                {"role": "system", "content": sys},
                {"role": "user", "content": user},
            ],
            response_format={"type": "json_object"},
            temperature=0.2,
        )
        txt = resp.choices[0].message.content or ""
        data = _extract_json(txt)
        cand = data.get("issues") if isinstance(data, dict) else data
        if isinstance(cand, list):
            for it in cand[:6]:
                issue = str(it.get("issue") or "").strip()
                if not issue:
                    continue
                weight = float(it.get("weight", 0.0))
                keywords = [str(k).strip() for k in (it.get("keywords") or []) if str(k).strip()]
                issues.append({"issue": issue[:80], "weight": max(0.0, min(1.0, weight)), "keywords": keywords[:6]})
    except Exception:
        pass
    # フォールバック
    if not issues:
        issues = [
            {"issue": "情報共有の改善", "weight": 0.34, "keywords": ["ナレッジ共有", "コミュニケーション", "ドキュメント"]},
            {"issue": "コスト最適化", "weight": 0.33, "keywords": ["費用削減", "効率化", "自動化"]},
            {"issue": "セキュリティ強化", "weight": 0.33, "keywords": ["アクセス管理", "監査", "権限"]},
        ]
    # 正規化
    s = sum(x["weight"] for x in issues) or 1.0
    for x in issues:
        x["weight"] = float(x["weight"] / s)
    return issues


def _normalize_concat_row(row: pd.Series) -> str:
    """name, category, tags, description を連結して正規化"""
    s = f"{row.get('name','')} {row.get('category','')} {row.get('tags','')} {row.get('description','')}"
    s = s.lower()
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _embed_texts(client, texts: List[str], embed_model: str, is_azure: bool) -> np.ndarray:
    """
    Embedding API を呼び出しベクトルを返す。失敗時は例外を送出。
    """
    try:
        # Azure でも OpenAI でも embeddings.create は同じ形で呼べる
        resp = client.embeddings.create(model=embed_model, input=texts)
        vecs = np.array([d.embedding for d in resp.data], dtype="float32")
        return vecs
    except Exception as e:
        raise RuntimeError(f"embedding failed: {e}")


def _build_products_index(dataset: str, df: pd.DataFrame, client, embed_model: str, is_azure: bool) -> Dict[str, Any]:
    """
    products DataFrame から埋め込み索引用インデックスを構築しキャッシュする。
    Cache key: dataset_name + length + embed_model
    """
    key = f"{dataset}:{len(df)}:{embed_model}"
    cache = st.session_state.get("_emb_cache", {})
    if key in cache:
        return cache[key]
    # テキスト生成
    texts = [_normalize_concat_row(row) for _, row in df.iterrows()]
    try:
        vecs = _embed_texts(client, texts, embed_model, is_azure)
        index = {"vecs": vecs, "ids": df["id"].astype(str).tolist(), "df": df, "model": embed_model}
    except Exception:
        # フォールバック: TF-IDF
        try:
            from sklearn.feature_extraction.text import TfidfVectorizer
            vectorizer = TfidfVectorizer(min_df=1)
            vecs = vectorizer.fit_transform(texts)
            index = {"vecs": vecs, "ids": df["id"].astype(str).tolist(), "df": df, "model": "tfidf", "vectorizer": vectorizer}
        except Exception:
            index = {"vecs": None, "ids": [], "df": df, "model": None}
    cache[key] = index
    st.session_state._emb_cache = cache
    return index


def _retrieve_by_issues(index: Dict[str, Any], issues: List[Dict[str, Any]], client, embed_model: str, is_azure: bool, top_pool: int) -> List[Dict[str, Any]]:
    """
    課題の重み付きベクトルで類似検索し、上位 top_pool 件を返す。
    index["vecs"] が None または TF-IDF の場合は空リストを返す。
    """
    if not issues or not index or index.get("vecs") is None:
        return []
    vecs = index["vecs"]
    # TF-IDF の場合は類似検索を行わない
    if hasattr(vecs, "toarray") or index.get("model") == "tfidf":
        return []
    # クエリベクトル
    queries = [f"{it['issue']} {' '.join(it.get('keywords') or [])}".strip() for it in issues]
    weights = np.array([float(it.get("weight", 0.0)) for it in issues], dtype="float32")
    try:
        q_embs = _embed_texts(client, queries, embed_model, is_azure)
        q = (weights[:, None] * q_embs).sum(axis=0, keepdims=True)
        # 正規化
        v_norm = vecs / (np.linalg.norm(vecs, axis=1, keepdims=True) + 1e-9)
        q_norm = q / (np.linalg.norm(q, axis=1, keepdims=True) + 1e-9)
        sims = np.dot(q_norm, v_norm.T).ravel()
        order = sims.argsort()[::-1][:max(1, top_pool)]
        out = []
        for idx_pos in order:
            rid = index["ids"][idx_pos]
            row = index["df"].iloc[idx_pos].to_dict()
            out.append({
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
                "score": float(sims[idx_pos]),
                "reason": f"課題と高類似 ({sims[idx_pos]:.3f})",
            })
        return out
    except Exception:
        return []


# =========================
# 候補検索（CSV→粗選定→LLM選抜→LLM要約）
# =========================
def _search_product_candidates(
    company: str,
    item_id: Optional[str],
    meeting_notes: str,
    top_k: int,
    history_n: int,
    dataset: str,
    uploaded_files: List[Any],   # ここを活用（資料テキスト抽出）
) -> List[Dict[str, Any]]:
    # 企業分析の文脈
    ctx = _gather_messages_context(item_id, history_n)

    # CSV 読み込み
    df = _load_products_from_csv(dataset)
    if df.empty:
        return []

    # ★ 追加：アップロード資料からテキスト抽出
    uploads_text = _extract_text_from_uploads(uploaded_files) if uploaded_files else ""

    # ☆ 変更：課題抽出に uploads_text を渡す
    issues = _analyze_pain_points(meeting_notes or "", ctx or "", uploads_text)

    # 埋め込みモデルと環境判定
    use_azure = os.getenv("USE_AZURE", "").lower() == "true" or bool(os.getenv("AZURE_OPENAI_ENDPOINT"))
    embed_model = os.getenv("AZURE_OPENAI_EMBED_DEPLOYMENT") if use_azure else os.getenv("EMBED_MODEL", "text-embedding-3-small")

    # LLM クライアント取得
    client, _ = _get_chat_client()

    # 埋め込みインデックス構築
    index = _build_products_index(dataset, df, client, embed_model, use_azure)

    # 課題ドリブン粗候補検索（Top-pool）
    top_pool = max(40, top_k * 4)
    pool = _retrieve_by_issues(index, issues, client, embed_model, use_azure, top_pool)
    # フォールバック：語句一致で粗選定
    if not pool:
        pool = _fallback_rank_products(meeting_notes, ctx, df, top_pool=max(40, top_k * 3))

    # LLM で精選（課題付）
    try:
        selected = _llm_pick_products(pool, top_k, company, meeting_notes, ctx, issues)
        if not selected:
            selected = pool[:top_k]
    except Exception:
        selected = pool[:top_k]

    # 各製品の 80字概要を LLM 要約（失敗時は短縮）
    _summarize_overviews_llm(selected)
    return selected


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


# =========================
# メイン描画（フロント改修のみ）
# =========================
def render_slide_generation_page():
    """スライド作成ページ（フロント配置を変更：上段＝商談詳細＆資料、下段＝課題分析＆候補カード）"""
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
        
        st.session_state.slide_use_gpt_api = st.checkbox(
            "GPT API使用",
            value=st.session_state.slide_use_gpt_api,
            key="slide_use_gpt_api_checkbox",
            help="Azure OpenAI GPT-5-miniを使用して企業課題分析と製品情報要約を行います"
        )
        
        st.session_state.slide_use_tavily_api = st.checkbox(
            "TAVILY API使用",
            value=st.session_state.slide_use_tavily_api,
            key="slide_use_tavily_api_checkbox",
            help="TAVILY APIを使用して製品情報のウェブ検索を行います"
        )
        
        if st.session_state.slide_use_tavily_api:
            st.session_state.slide_tavily_uses = st.number_input(
                "TAVILY API呼び出し回数（製品あたり）",
                min_value=1, max_value=5, value=st.session_state.slide_tavily_uses, step=1,
                key="slide_tavily_uses_input",
                help="各製品に対してTAVILY APIを何回呼び出すかを指定します"
            )

        sidebar_clear = st.button("クリア", use_container_width=True, help="候補を画面内でクリア")

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

    # ====================== 上段：商談詳細（大）＆参考資料（横並び） ======================
    top_l, top_r = st.columns([3, 2], gap="large")  # 商談詳細を大きめに
    with top_l:
        st.markdown("**● 商談の詳細**")
        st.text_area(
            label="商談の詳細",
            key="slide_meeting_notes",
            height=200,
            label_visibility="collapsed",
            placeholder="例：来期の需要予測精度向上と在庫最適化。PoCから段階導入… など",
        )
    with top_r:
        st.markdown("**● 参考資料**")
        uploads = st.file_uploader(
            label="参考資料（任意）",
            type=["pdf", "pptx", "docx", "csv", "png", "jpg", "jpeg", "txt"],
            accept_multiple_files=True,
            key="slide_uploader",
            label_visibility="collapsed",
            help="アップロード資料は特徴抽出/要約に利用（今回の修正で課題抽出に反映されます）。",
        )
        if uploads:
            st.session_state.uploaded_files_store = uploads
            st.success(f"{len(uploads)} ファイルを受け付けました。")
        elif st.session_state.uploaded_files_store:
            st.caption(f"前回アップロード済み: {len(st.session_state.uploaded_files_store)} ファイル")

    # 「候補を取得」押下時：従来の候補検索（バックロジックは変更なし）＋ UI表示用の課題分析結果を計算
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

            # 表示用：課題分析（※候補選定ロジックには影響しない）
            ctx_for_view = _gather_messages_context(item_id, int(st.session_state.slide_history_reference_count))
            uploads_text_for_view = _extract_text_from_uploads(st.session_state.uploaded_files_store) if st.session_state.uploaded_files_store else ""
            st.session_state.analyzed_issues = _analyze_pain_points(
                st.session_state.slide_meeting_notes or "",
                ctx_for_view or "",
                uploads_text_for_view or ""
            )

    if sidebar_clear:
        st.session_state.product_candidates = []
        st.session_state.analyzed_issues = []
        st.info("候補と課題分析表示をクリアしました。")

    st.divider()

    # ====================== 下段：左＝課題分析／右＝候補カード ======================
    bottom_l, bottom_r = st.columns([5, 7], gap="large")

    with bottom_l:
        st.markdown("**● 課題分析（自動）**")
        issues = st.session_state.get("analyzed_issues") or []
        if not issues:
            st.caption("『候補を取得』を押すと、商談メモ・履歴・参考資料から課題を自動抽出して表示します。")
        else:
            for i, it in enumerate(issues, start=1):
                with st.container(border=True):
                    st.markdown(f"**{i}. {it.get('issue','—')}**")
                    st.caption(f"重み: {it.get('weight',0):.2f}")
                    kws = it.get("keywords") or []
                    if kws:
                        st.markdown("キーワード: " + " / ".join(kws))

    with bottom_r:
        st.markdown("**● 候補（カード表示）**")
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

    # ====================== 2. スライド生成 ======================
    # テンプレート情報の表示
    if st.button("📋 テンプレート情報を表示", help="使用するテンプレートの詳細情報を表示します"):
        try:
            generator = NewSlideGenerator()
            template_info = generator.get_template_info()
            st.json(template_info)
        except Exception as e:
            st.error(f"テンプレート情報の取得でエラーが発生しました: {e}")

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
        elif not st.session_state.product_candidates:
            st.error("製品候補がありません。先に「候補を取得」を押してください。")
        else:
            selected = list(st.session_state.product_candidates or [])  # 全候補を採用
            
            # 下書きの作成
            outline = _make_outline_preview(
                company_internal,
                st.session_state.slide_meeting_notes or "",
                selected,
                st.session_state.slide_overview or "",
            )
            st.session_state.slide_outline = outline
            
            # プレゼンテーション生成
            with st.spinner("AIエージェントがプレゼンテーションを生成中..."):
                try:
                    print(f"🚀 Streamlit: プレゼンテーション生成開始")
                    print(f"  企業名: {company_internal}")
                    print(f"  製品数: {len(selected)}")
                    print(f"  GPT API: {st.session_state.slide_use_gpt_api}")
                    print(f"  TAVILY API: {st.session_state.slide_use_tavily_api}")
                    print(f"  TAVILY使用回数: {st.session_state.slide_tavily_uses}")
                    
                    # チャット履歴の取得
                    print("📚 チャット履歴取得中...")
                    chat_history = _gather_messages_context(
                        item_id, 
                        st.session_state.slide_history_reference_count
                    )
                    print(f"  チャット履歴長: {len(chat_history)}文字")
                    
                    print("🤖 NewSlideGenerator初期化中...")
                    generator = NewSlideGenerator()
                    print("✅ NewSlideGenerator初期化完了")
                    
                    print("🎯 プレゼンテーション生成実行中...")
                    pptx_data = generator.create_presentation(
                        project_name=company_internal,  # 案件名として企業名を使用
                        company_name=company_internal,
                        meeting_notes=st.session_state.slide_meeting_notes or "",
                        chat_history=chat_history,
                        products=selected,
                        use_tavily=st.session_state.slide_use_tavily_api,
                        use_gpt=st.session_state.slide_use_gpt_api,
                        tavily_uses=st.session_state.slide_tavily_uses
                    )
                    
                    # ダウンロードボタンの表示
                    print("✅ プレゼンテーション生成完了")
                    print(f"  生成されたデータサイズ: {len(pptx_data)} バイト")
                    
                    st.success("プレゼンテーションが生成されました！")
                    
                    # ファイル名の生成
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
                    print(f"❌ Streamlit: プレゼンテーション生成でエラーが発生: {e}")
                    st.error(f"プレゼンテーション生成でエラーが発生しました: {e}")
                    st.info("下書きのみ作成されました。")

    if st.session_state.slide_outline:
        with st.expander("下書きプレビュー（JSON）", expanded=True):
            st.json(st.session_state.slide_outline)
