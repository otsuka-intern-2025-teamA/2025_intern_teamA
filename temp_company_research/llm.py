# llm.py
import requests
from typing import List
from data import CompanyReport
from config import get_settings

def company_briefing(company: str) -> CompanyReport:
    """
    バックエンド /report (FastAPIパイプライン Tavily + Azure OpenAI) を呼び出し、
    フロントエンド用の CompanyReport 構造体にマッピングします。
    """
    s = get_settings()
    url = s.backend_url.rstrip("/") + "/report"

    payload = {
        "company_name": company,
        "locale": "ja",
        "sections": ["profile", "products", "market", "financials", "news"]
    }
    r = requests.post(url, json=payload, timeout=120)
    if r.status_code != 200:
        raise RuntimeError(f"Backend error {r.status_code}: {r.text}")

    data = r.json()
    # バックエンドは { company, markdown, sources, meta, briefings } を返すことを期待
    brief = (data.get("briefings") or {})  # dict: section -> text
    sources_raw = data.get("sources") or []  # [{id, url, title}, ...]

    # UI用にリンクをシンプルな文字列リストに変換
    sources: List[str] = []
    for ssrc in sources_raw:
        if isinstance(ssrc, dict):
            title = ssrc.get("title") or ssrc.get("url") or ""
            url2 = ssrc.get("url") or ""
            sources.append(f"{title} — {url2}".strip(" —"))
        elif isinstance(ssrc, str):
            sources.append(ssrc)

    # セクションのマッピング（最低限）
    overview = brief.get("profile", "")
    offerings = brief.get("products", "")
    market_block = brief.get("market", "")
    financials = brief.get("financials", "")
    news = brief.get("news", "")
    risks = brief.get("risks", "")

    # フィールド
    return CompanyReport(
        company=company,
        overview=overview,
        offerings=offerings,
        customers_and_markets=(market_block + ("\n\n" + financials if financials else "")),
        recent_news=news,
        competitors="",  # 必要なら market_block から抽出可能
        risks=risks,
        suggested_questions=[],
        sources=sources,
    )
