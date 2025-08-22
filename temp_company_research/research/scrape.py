import asyncio
import os
from typing import List, Dict, Optional

import httpx
import trafilatura

TIMEOUT = float(os.getenv("REQUEST_TIMEOUT_SECONDS", "25"))
CONC = int(os.getenv("CONCURRENT_FETCHES", "6"))

REQUEST_HEADERS = {
    "User-Agent": "CompanyResearchBot/0.1 (+https://example.org)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

__all__ = ["fetch_and_extract"] 

def _clip(s: str, limit: int) -> str:
    return s if len(s) <= limit else s[:limit]

def _extract_title(html: str, url: str) -> Optional[str]:
    try:
        meta = trafilatura.metadata.extract_metadata(html, url=url)
        return meta.title if meta else None
    except Exception:
        return None

async def _fetch(url: str) -> Optional[str]:
    try:
        async with httpx.AsyncClient(
            timeout=TIMEOUT, headers=REQUEST_HEADERS, follow_redirects=True
        ) as client:
            r = await client.get(url)
            r.raise_for_status()
            return r.text
    except Exception:
        return None

async def fetch_and_extract(urls: List[str]) -> List[Dict]:
    """
    非同期でページをダウンロードし、Trafilaturaでテキストを抽出します。
    戻り値は辞書のリスト: {url, title, text}
    """
    sem = asyncio.Semaphore(CONC)
    out: List[Dict] = []

    async def one(u: str):
        async with sem:
            html = await _fetch(u)
            if not html:
                return
            try:
                text = trafilatura.extract(
                    html, url=u, include_comments=False, output_format="txt"
                )
            except Exception:
                text = None
            if text and len(text) > 300:
                title = _extract_title(html, u) or ""
                out.append({"url": u, "title": title, "text": _clip(text, 60000)})

    await asyncio.gather(*[one(u) for u in urls])
    return out
