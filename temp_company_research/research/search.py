import os
import httpx
from typing import List, Tuple, Dict,Awaitable
import urllib.parse

TAVILY_URL = "https://api.tavily.com/search"
TIMEOUT = float(os.getenv("REQUEST_TIMEOUT_SECONDS", "25"))

HEADERS = {
    "Content-Type": "application/json",
    "User-Agent": "CompanyResearchBot/0.1 (+https://example.org)"
}

def _tavily_payload(query: str, max_results: int = 8) -> dict:
    return {
        "api_key": os.environ["TAVILY_API_KEY"],
        "query": query,
        "max_results": max_results,
        "search_depth": "advanced",
        "include_answer": False,
        "include_raw_content": False,
        "include_domains": [],
        "exclude_domains": []
    }

async def tavily_search(query: str, k: int = 8) -> List[str]:
    payload = _tavily_payload(query, k)
    async with httpx.AsyncClient(timeout=TIMEOUT, headers=HEADERS) as client:
        r = await client.post(TAVILY_URL, json=payload)
        r.raise_for_status()
        data = r.json()
        urls = [item["url"] for item in data.get("results", []) if item.get("url")]
        # UTMパラメータの簡易クリーニング
        return [_strip_tracking(u) for u in urls]

def _strip_tracking(url: str) -> str:
    try:
        p = urllib.parse.urlparse(url)
        q = urllib.parse.parse_qsl(p.query, keep_blank_values=True)
        q = [(k, v) for (k, v) in q if not k.lower().startswith("utm_")]
        new_q = urllib.parse.urlencode(q)
        return urllib.parse.urlunparse((p.scheme, p.netloc, p.path, p.params, new_q, p.fragment))
    except Exception:
        return url

async def resolve_company(name: str) -> Tuple[str, List[str]]:
    """
    （正規化された会社名、有用なスタートURLリスト）を返します。
    MVPロジック：公式サイト・Wikipedia・投資家向けページを上位から取得します。
    """
    q = f"{name} official site OR investors OR wikipedia"
    urls = await tavily_search(q, k=6)
    # スクレイピング時にタイトルで正規化しますが、ここでは入力値を返します
    return name.strip(), urls

async def search_buckets(company_name: str) -> Dict[str, List[str]]:
    """
    テーマ別クエリを準備します：プロフィール、製品、マーケット、財務、ニュース。
    """
    queries = {
        "profile": f"{company_name} company overview business model",
        "products": f"{company_name} products services portfolio customers",
        "market": f"{company_name} competitors industry market share",
        "financials": f"{company_name} financial results revenue operating income funding",
        "news": f"{company_name} recent news last 12 months"
    }
    # Tavilyによる並列検索
    results = await _gather_dict({k: tavily_search(v, k=8) for k, v in queries.items()})
    # 各バケットでの簡易重複排除
    return {k: list(dict.fromkeys(v)) for k, v in results.items()}

async def _gather_dict(tasks: Dict[str, Awaitable[List[str]]]) -> Dict[str, List[str]]:
    import asyncio
    keys = list(tasks.keys())
    vals = await asyncio.gather(*[tasks[k] for k in keys])
    return dict(zip(keys, vals))
