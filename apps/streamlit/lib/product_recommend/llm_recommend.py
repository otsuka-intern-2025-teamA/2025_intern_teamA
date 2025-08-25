# apps/streamlit/lib/product_recommend/llm_recommend.py

from __future__ import annotations
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import hashlib, json, math, re
import pandas as pd
import numpy as np

from openai import OpenAI, AzureOpenAI

from .config_recommend import get_settings_recommend
from .data_recommend import ProductItem, ProductRecommendation

# ============ クライアント/モデル名 ============
def _get_client():
    s = get_settings_recommend()
    if s.use_azure:
        return AzureOpenAI(api_version=s.api_version, azure_endpoint=s.azure_endpoint, api_key=s.azure_api_key)
    return OpenAI(api_key=s.openai_api_key)

def _chat_model_name() -> str:
    s = get_settings_recommend()
    if s.use_azure and s.azure_chat_deployment:
        return s.azure_chat_deployment
    return s.default_model

def _can_use_embeddings() -> bool:
    """埋め込み用デプロイ/モデルが設定されているかだけで判定（未設定なら使わない）"""
    s = get_settings_recommend()
    if s.use_azure:
        return bool(s.azure_embed_deployment)  # Azureは“デプロイ名”が必要
    return bool(s.default_embed_model)         # OpenAI直の場合はモデル名

def _embed_model_name() -> str:
    s = get_settings_recommend()
    if s.use_azure and s.azure_embed_deployment:
        return s.azure_embed_deployment
    return s.default_embed_model

# ============ CSV カタログ ============
def _pick_first(row: pd.Series, *cols) -> str:
    for c in cols:
        if c in row and pd.notna(row[c]) and str(row[c]).strip():
            return str(row[c]).strip()
    return ""

def _row_to_item(row: pd.Series) -> ProductItem:
    pid  = _pick_first(row, "id","product_id","sku","コード")
    name = _pick_first(row, "name","product_name","title","商品名")
    cat  = _pick_first(row, "category","カテゴリ","class") or None
    desc = _pick_first(row, "description","desc","詳細","spec","仕様") or None
    tags = _pick_first(row, "tags","キーワード","keywords") or None
    price: Optional[float] = None
    for c in ("price","単価","価格","list_price"):
        if c in row and pd.notna(row[c]):
            try:
                price = float(row[c]); break
            except Exception:
                pass
    if not pid:
        pid = name or f"ROW-{hashlib.md5(str(row.values).encode()).hexdigest()[:8]}"
    return ProductItem(id=pid, name=name or "(No Name)", category=cat, price=price, description=desc, tags=tags)

def load_catalog(dataset_dir: Path) -> List[ProductItem]:
    paths = list(dataset_dir.glob("*.csv"))
    if not paths:
        raise FileNotFoundError(f"商材CSVが見つかりません: {dataset_dir}")
    dfs = []
    for p in paths:
        try:
            dfs.append(pd.read_csv(p))
        except UnicodeDecodeError:
            dfs.append(pd.read_csv(p, encoding="cp932", errors="ignore"))
    df = pd.concat(dfs, ignore_index=True).replace({np.nan: None})
    items = [_row_to_item(r) for _, r in df.iterrows()]
    seen, uniq = set(), []
    for it in items:
        k = (it.id, it.name)
        if k in seen: continue
        seen.add(k); uniq.append(it)
    return uniq

# ============ 表現文生成 ============
def _as_search_text(p: ProductItem) -> str:
    parts = [p.name]
    if p.category: parts.append(f"カテゴリ:{p.category}")
    if p.price is not None: parts.append(f"価格:¥{int(p.price):,}")
    if p.tags: parts.append(f"タグ:{p.tags}")
    if p.description: parts.append(p.description)
    return " / ".join(parts)

# ============ （A）埋め込み粗選定（設定されている場合のみ使用） ============
def _rank_by_embeddings(products: List[ProductItem], query_text: str, embed_model: str, client) -> List[tuple[ProductItem, float]]:
    resp_prod = client.embeddings.create(model=embed_model, input=[_as_search_text(p) for p in products])
    prod_vecs = np.vstack([np.array(d.embedding, dtype=np.float32) for d in resp_prod.data])
    resp_q = client.embeddings.create(model=embed_model, input=[query_text])
    q_vec = np.array(resp_q.data[0].embedding, dtype=np.float32)[None, :]
    prod_vecs = prod_vecs / (np.linalg.norm(prod_vecs, axis=1, keepdims=True) + 1e-8)
    q_vec = q_vec / (np.linalg.norm(q_vec, axis=1, keepdims=True) + 1e-8)
    sim = prod_vecs @ q_vec.T
    sim = sim[:, 0]
    idx = np.argsort(-sim)
    return [(products[i], float(sim[i])) for i in idx]

# ============ （B）ローカルTF-IDF粗選定（埋め込み未設定/失敗時はこちら） ============
_nonword = re.compile(r"[^\w\u3040-\u30ff\u3400-\u9fff]+", re.UNICODE)
def _char_ngrams(s: str, n_min=2, n_max=4) -> List[str]:
    if not s: return []
    base = _nonword.sub("", s)
    if not base: return []
    grams = []
    L = len(base)
    for n in range(n_min, n_max+1):
        if L < n: continue
        grams += [base[i:i+n] for i in range(L-n+1)]
    return grams

def _build_idf(docs: List[str], n_min=2, n_max=4):
    df: Dict[str,int] = {}
    doc_tfs: List[Dict[str,int]] = []
    for s in docs:
        grams = _char_ngrams(s, n_min, n_max)
        tf: Dict[str,int] = {}
        for g in grams:
            tf[g] = tf.get(g,0)+1
        doc_tfs.append(tf)
        for g in tf.keys():
            df[g] = df.get(g,0)+1
    N = max(1, len(docs))
    idf = {g: math.log((N+1)/(c+1)) + 1.0 for g,c in df.items()}
    return idf, doc_tfs

def _tfidf_rank(products: List[ProductItem], query_text: str) -> List[tuple[ProductItem, float]]:
    docs = [" ".join(filter(None, [p.name, p.category or "", p.tags or "", p.description or ""])) for p in products]
    idf, doc_tfs = _build_idf(docs)
    # クエリをn-gram化してスコアリング
    q_tf: Dict[str,int] = {}
    for g in _char_ngrams(query_text):
        q_tf[g] = q_tf.get(g,0)+1
    scored: List[tuple[ProductItem, float]] = []
    for p, tf in zip(products, doc_tfs):
        common = set(q_tf.keys()) & set(tf.keys())
        score = sum((q_tf[g]) * idf.get(g, 0.0) for g in common)
        scored.append((p, float(score)))
    scored.sort(key=lambda x: -x[1])
    return scored

# ============ LLM 最終選抜（JSONモード優先） ============
_SYSTEM = (
    "あなたはB2Bプリセールスの提案プランナーです。"
    "文脈に合う製品を選定し、日本語で短い理由を付けます。"
    "出力は指定JSONのみ。捏造禁止。"
)
_JSON_GUIDE = (
    '出力は以下のJSONのみ（前後の文章は禁止）:\n'
    '{ "recommendations": ['
    '{"product_id":"<catalog id>","reason":"<120字以内>","confidence":0.0}'
    '] }'
)

def _llm_pick(top_pool: List[ProductItem], top_k: int, company: str, meeting_notes: str, chat_history_text: str) -> List[Dict[str, Any]]:
    client = _get_client()
    model = _chat_model_name()
    catalog = "\n\n".join([f"- ID:{p.id}\n{_as_search_text(p)}" for p in top_pool])
    user = f"""# 企業
{company}

# 商談の要点
{meeting_notes or "(なし)"}

# 企業分析チャット抜粋
{chat_history_text or "(なし)"}

# 候補（粗選定済み）
{catalog}

# 指示
上の候補のみから Top-{top_k} を選び、{_JSON_GUIDE}
"""
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role":"system","content":_SYSTEM},{"role":"user","content":user}],
            response_format={"type": "json_object"},
        )
    except Exception:
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role":"system","content":_SYSTEM},{"role":"user","content":user}],
        )
    text = (resp.choices[0].message.content or "").strip()
    try:
        data = json.loads(text) if text.startswith("{") else {}
        recs = data.get("recommendations", []) or []
        out: List[Dict[str, Any]] = []
        for r in recs[:top_k]:
            pid = str(r.get("product_id","")).strip()
            if not pid: continue
            out.append({
                "product_id": pid,
                "reason": str(r.get("reason","")).strip(),
                "confidence": float(r.get("confidence", 0.0)),
            })
        return out
    except Exception:
        return []

# ============ 外部公開 API ============
def recommend_products(
    *,
    dataset_dir: Path,
    company: str,
    meeting_notes: str,
    chat_history_text: str,
    top_k: int = 10,
) -> List[ProductRecommendation]:
    """
    1) 粗選定
       - 埋め込みが設定されていれば Embeddings
       - 無ければ ローカルTF-IDF
    2) LLMで Top-K を厳選＋理由生成
       - 失敗時は粗選定順に簡易理由で返す
    """
    products = load_catalog(dataset_dir)

    # 粗選定
    query = "\n".join([
        f"企業名:{company}",
        f"商談詳細:{meeting_notes}",
        f"企業分析抜粋:{chat_history_text}",
    ])
    rough_k = max(40, top_k * 3)
    ranked: List[tuple[ProductItem, float]] = []
    if _can_use_embeddings():
        try:
            client = _get_client()
            ranked = _rank_by_embeddings(products, query, _embed_model_name(), client)
        except Exception:
            ranked = []
    if not ranked:
        ranked = _tfidf_rank(products, query)

    pool = [p for p, _ in ranked[:rough_k]]

    # LLMで最終選抜
    picks = _llm_pick(pool, top_k, company, meeting_notes, chat_history_text)

    prod_map = {p.id: p for p in products}
    out: List[ProductRecommendation] = []
    if picks:
        for r in picks[:top_k]:
            p = prod_map.get(r["product_id"])
            if not p: continue
            out.append(ProductRecommendation(
                id=p.id, name=p.name, category=p.category, price=p.price,
                score=float(max(0.0, min(1.0, r.get("confidence", 0.0)))),
                reason=r.get("reason",""),
            ))
        return out

    # フォールバック（理由は簡易）
    top = pool[:top_k]
    for p in top:
        out.append(ProductRecommendation(
            id=p.id, name=p.name, category=p.category, price=p.price,
            score=0.5,  # 粗選定からの一律値（必要なら計算に置換）
            reason="商談文脈との関連度が高い候補（粗選定）",
        ))
    return out
