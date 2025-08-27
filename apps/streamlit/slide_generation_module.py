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

import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any
import tempfile

import numpy as np
import pandas as pd

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv(".env", override=True)

# APIクライアント（企業分析のチャット履歴取得に使用）
from lib.api import api_available, get_api_client

# スライド生成モジュール
# 共通スタイル
from lib.styles import (
    apply_company_analysis_page_styles,  # サイドバー圧縮/ロゴカード/下寄せCSSを流用
    apply_main_styles,
    apply_slide_generation_page_styles,
    apply_title_styles,
    render_sidebar_logo_card,
    render_slide_generation_title,  # タイトル描画（h1.slide-generation-title）
)

import streamlit as st

# 画像/データパス
PROJECT_ROOT = Path(__file__).parent.parent.parent
LOGO_PATH = PROJECT_ROOT / "data" / "images" / "otsuka_logo.jpg"
ICON_PATH = PROJECT_ROOT / "data" / "images" / "otsuka_icon.png"
PRODUCTS_DIR = PROJECT_ROOT / "data" / "csv" / "products"
PLACEHOLDER_IMG = PROJECT_ROOT / "data" / "images" / "product_placeholder.png"

# --- 新スライド生成システム ---
from lib.new_slide_generator import NewSlideGenerator


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
    ss.setdefault("slide_top_k", 1)                   # 提案件数（デフォ1）
    ss.setdefault("slide_products_dataset", "Auto")    # 商材データセット選択
    ss.setdefault("slide_use_tavily_api", True)        # TAVILY API使用フラグ
    ss.setdefault("slide_use_gpt_api", True)           # GPT API使用フラグ
    ss.setdefault("slide_tavily_uses", 1)              # 製品あたりのTAVILY API呼び出し回数
    # 埋め込み検索用キャッシュ
    ss.setdefault("_emb_cache", {})
    # 表示用：課題分析結果（UIで見せるだけ。選定ロジックは従来通り）
    ss.setdefault("analyzed_issues", [])
    ss.setdefault("slide_template_bytes", None)
    ss.setdefault("slide_template_name", None)


# =========================
# 新スライド生成システム用のヘルパー関数
# =========================
def _get_proposal_issues_from_db(proposal_id: str) -> list[dict[str, Any]]:
    """データベースから提案課題を取得"""
    try:
        import sqlite3
        db_path = PROJECT_ROOT / "data" / "sqlite" / "app.db"
        if not db_path.exists():
            return []
        
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT idx, issue, weight, keywords_json 
                FROM proposal_issues 
                WHERE proposal_id = ? 
                ORDER BY idx
            """, (proposal_id,))
            
            rows = cursor.fetchall()
            issues = []
            for row in rows:
                import json
                keywords = json.loads(row[3]) if row[3] else []
                issues.append({
                    "issue": row[1],
                    "weight": row[2],
                    "keywords": keywords
                })
            
            return issues
    except Exception as e:
        print(f"提案課題取得エラー: {e}")
        return []


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
def _list_product_datasets() -> list[str]:
    """productsディレクトリ配下のサブフォルダ名を列挙（Autoを先頭）"""
    if not PRODUCTS_DIR.exists():
        return ["Auto"]
    ds = ["Auto"]
    for p in PRODUCTS_DIR.iterdir():
        if p.is_dir():
            ds.append(p.name)
    return ds


def _gather_messages_context(item_id: str | None, history_n: int) -> str:
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


# =========================
# 参考資料（アップロードファイル）テキスト抽出【追加】
# =========================
def _extract_text_from_uploads(uploaded_files: list[Any], max_chars: int = 12000) -> str:
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

    chunks: list[str] = []
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
                    import io

                    from pypdf import PdfReader  # pip install pypdf
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
def _simple_tokenize(text: str) -> list[str]:
    text = str(text or "").lower()
    text = re.sub(r"[^a-z0-9\u3040-\u30ff\u4e00-\u9fff]+", " ", text)
    toks = text.split()
    return [t for t in toks if len(t) >= 2]


def _fallback_rank_products(
    notes: str,
    messages_ctx: str,
    products_df: pd.DataFrame,
    top_pool: int
) -> list[dict[str, Any]]:
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

    scored: list[tuple[float, dict[str, Any]]] = []
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
# 製品概要生成（簡易版）
# =========================
def _generate_product_overview(product: dict[str, Any]) -> str:
    """製品の概要を生成（80字以内）"""
    description = product.get("description") or ""
    tags = product.get("tags") or ""
    name = product.get("name") or ""
    
    # 説明文から概要を生成
    if description:
        overview = description[:80]
        if len(description) > 80:
            overview += "..."
        return overview
    
    # タグから概要を生成
    if tags:
        overview = f"{name}: {tags[:60]}"
        if len(tags) > 60:
            overview += "..."
        return overview
    
    # 名前のみ
    return name if name else "製品の詳細情報がありません"


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

# =========================
# 新スライド生成システム用のヘルパー関数（続き）
# =========================
def _analyze_pain_points_simple(notes: str, messages_ctx: str, uploads_text: str = "") -> list[dict[str, Any]]:
    """
    簡易版課題分析（LLMを使用しない）
    商談メモ・会話文脈・アップロード資料から基本的な課題を抽出
    """
    issues = []
    
    # 基本的な課題パターン
    basic_issues = [
        {"issue": "業務効率化", "weight": 0.4, "keywords": ["効率化", "自動化", "生産性"]},
        {"issue": "コスト最適化", "weight": 0.3, "keywords": ["費用削減", "最適化", "コスト"]},
        {"issue": "情報管理改善", "weight": 0.3, "keywords": ["情報共有", "管理", "システム"]}
    ]
    
    # テキスト内容に基づいて重みを調整
    all_text = f"{notes} {messages_ctx} {uploads_text}".lower()
    
    if "効率" in all_text or "生産性" in all_text:
        basic_issues[0]["weight"] = 0.5
        basic_issues[1]["weight"] = 0.25
        basic_issues[2]["weight"] = 0.25
    elif "コスト" in all_text or "費用" in all_text:
        basic_issues[0]["weight"] = 0.25
        basic_issues[1]["weight"] = 0.5
        basic_issues[2]["weight"] = 0.25
    elif "情報" in all_text or "管理" in all_text:
        basic_issues[0]["weight"] = 0.25
        basic_issues[1]["weight"] = 0.25
        basic_issues[2]["weight"] = 0.5
    
    return basic_issues


# =========================
# 候補検索（簡易版）
# =========================
def _search_product_candidates(
    company: str,
    item_id: str | None,
    meeting_notes: str,
    top_k: int,
    history_n: int,
    dataset: str,
    uploaded_files: list[Any],
) -> list[dict[str, Any]]:
    # 企業分析の文脈
    ctx = _gather_messages_context(item_id, history_n)

    # CSV 読み込み
    df = _load_products_from_csv(dataset)
    if df.empty:
        return []

    # アップロード資料からテキスト抽出
    uploads_text = _extract_text_from_uploads(uploaded_files) if uploaded_files else ""

    # 簡易版課題分析
    issues = _analyze_pain_points_simple(meeting_notes or "", ctx or "", uploads_text)

    # 語句一致で粗選定
    top_pool = max(40, top_k * 4)
    pool = _fallback_rank_products(meeting_notes, ctx, df, top_pool=top_pool)

    # 上位K件を選択
    selected = pool[:top_k]
    
    # 各製品の概要を生成
    for product in selected:
        product["overview"] = _generate_product_overview(product)
    
    return selected


# =========================
# ドラフト作成
# =========================
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

# --- 提案保存ユーティリティ（既存 app.db を活用） ---
import sqlite3, uuid, json as _json
DB_PATH = PROJECT_ROOT / "data" / "sqlite" / "app.db"  # ← ここだけパス変更

def _init_db_for_proposals():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("""CREATE TABLE IF NOT EXISTS proposals(
            id TEXT PRIMARY KEY,
            project_item_id TEXT,
            company TEXT NOT NULL,
            meeting_notes TEXT,
            overview TEXT,
            created_at TEXT NOT NULL
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS proposal_issues(
            proposal_id TEXT NOT NULL,
            idx INTEGER NOT NULL,
            issue TEXT NOT NULL,
            weight REAL,
            keywords_json TEXT,
            FOREIGN KEY(proposal_id) REFERENCES proposals(id)
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS proposal_products(
            proposal_id TEXT NOT NULL,
            rank INTEGER NOT NULL,
            product_id TEXT,
            name TEXT,
            category TEXT,
            price TEXT,
            reason TEXT,
            overview TEXT,
            score REAL,
            source_csv TEXT,
            image_url TEXT,
            FOREIGN KEY(proposal_id) REFERENCES proposals(id)
        )""")
        conn.commit()

def _save_proposal_to_db(
    project_item_id: str | None,
    company: str,
    meeting_notes: str,
    overview: str,
    issues: list[dict[str, Any]],
    products: list[dict[str, Any]],
    created_at_iso: str
) -> str:
    """提案ひとまとまりを保存し、proposal_id を返す（既存 app.db に追記）。"""
    _init_db_for_proposals()
    pid = str(uuid.uuid4())
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute(
            "INSERT INTO proposals(id, project_item_id, company, meeting_notes, overview, created_at) VALUES(?,?,?,?,?,?)",
            (pid, project_item_id, company, meeting_notes, overview, created_at_iso)
        )
        # 課題のスナップショット
        for i, it in enumerate(issues or []):
            c.execute(
                "INSERT INTO proposal_issues(proposal_id, idx, issue, weight, keywords_json) VALUES(?,?,?,?,?)",
                (pid, i+1, it.get('issue',''), float(it.get('weight') or 0.0), _json.dumps(it.get('keywords') or [], ensure_ascii=False))
            )
        # 採用製品のスナップショット
        for r, p in enumerate(products or []):
            c.execute(
                """INSERT INTO proposal_products(
                    proposal_id, rank, product_id, name, category, price, reason, overview, score, source_csv, image_url
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    pid, r+1,
                    str(p.get('id','')) or None,
                    p.get('name',''),
                    p.get('source_csv') or p.get('category',''),
                    str(p.get('price','')),
                    p.get('reason',''),
                    p.get('overview',''),
                    float(p.get('score') or 0.0),
                    p.get('source_csv') or '',
                    p.get('image_url') or ''
                )
            )
        conn.commit()
    return pid




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

        # --- ここから“数字はすべて一覧選択型” & Session State 既定値のみ使用 ---
        st.selectbox("提案件数", options=list(range(1, 11)), key="slide_top_k")

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
            height=154,
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
            st.session_state.analyzed_issues = _analyze_pain_points_simple(
                st.session_state.slide_meeting_notes or "",
                ctx_for_view or "",
                uploads_text_for_view or ""
            )
        # （任意）候補検索直後に“ドラフト”保存
        try:
            proposal_id = _save_proposal_to_db(
                project_item_id=item_id,
                company=company_internal,
                meeting_notes=st.session_state.slide_meeting_notes or "",
                overview=st.session_state.slide_overview or "",
                issues=st.session_state.analyzed_issues or [],
                products=st.session_state.product_candidates or [],
                created_at_iso=datetime.now().isoformat(timespec="seconds")
            )
            st.session_state["last_proposal_id"] = proposal_id
            st.info(f"ドラフト提案を保存しました（ID: {proposal_id[:8]}…）")
        except Exception as e:
            st.warning(f"ドラフト保存に失敗しました: {e}")


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
    # テンプレートの添付
    tmpl_file = st.file_uploader(
        "テンプレート（.pptx）を添付（任意）",
        type=["pptx"],
        key="slide_template_uploader",
        help="添付が無い場合は既定テンプレートを使用します"
    )

    # セッションへ保持
    if tmpl_file is not None:
        st.session_state.slide_template_bytes = tmpl_file.getvalue()
        st.session_state.slide_template_name = tmpl_file.name
        st.success(f"テンプレートを受け付けました：{tmpl_file.name}")
    else:
        # 既に前回アップロード済みなら名前だけ表示
        current = st.session_state.get("slide_template_name")
        if current:
            st.caption(f"現在のテンプレート：{current}（アップロード済みを使用）")
        else:
            st.caption("テンプレート未添付：既定テンプレートを使用します")

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
                    print("🚀 Streamlit: プレゼンテーション生成開始")
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
                    print("🤖 NewSlideGenerator初期化中.")

                    # アップロード済みテンプレがあれば一時ファイルに保存して使用
                    uploaded_template_path = None
                    try:
                        if st.session_state.get("slide_template_bytes"):
                            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pptx")
                            tmp.write(st.session_state["slide_template_bytes"])
                            tmp.flush()
                            tmp.close()
                            uploaded_template_path = tmp.name
                            print(f"  📎 アップロードテンプレ使用: {uploaded_template_path}")

                        generator = (NewSlideGenerator(template_path=uploaded_template_path) if uploaded_template_path else NewSlideGenerator())
                        print("✅ NewSlideGenerator初期化完了")
                    finally:
                        if uploaded_template_path and os.path.exists(uploaded_template_path):
                            try:
                                os.remove(uploaded_template_path)
                            except Exception:
                                pass
                    
                    # 提案課題の取得
                    print("🔍 提案課題取得中...")
                    proposal_issues = []
                    if st.session_state.get("last_proposal_id"):
                        proposal_issues = _get_proposal_issues_from_db(st.session_state["last_proposal_id"])
                    else:
                        proposal_issues = st.session_state.get("analyzed_issues", [])
                    
                    print(f"  提案課題数: {len(proposal_issues)}")
                    
                    print("🎯 プレゼンテーション生成実行中...")
                    pptx_data = generator.create_presentation(
                        project_name=company_internal,  # 案件名として企業名を使用
                        company_name=company_internal,
                        meeting_notes=st.session_state.slide_meeting_notes or "",
                        chat_history=chat_history,
                        products=selected,
                        proposal_issues=proposal_issues,
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
                    print(f"❌ Streamlit: プレゼンテーション生成でエラーが発生: {e}")
                    st.error(f"プレゼンテーション生成でエラーが発生しました: {e}")
                    st.info("下書きのみ作成されました。")

    if st.session_state.slide_outline:
        with st.expander("下書きプレビュー（JSON）", expanded=True):
            st.json(st.session_state.slide_outline)
