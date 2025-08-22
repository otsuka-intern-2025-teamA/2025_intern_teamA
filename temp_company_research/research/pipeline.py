# research/pipeline.py
import asyncio
from typing import List, Dict, Any

from research.search import resolve_company, search_buckets
from research.scrape import fetch_and_extract
from research.summarize import make_briefings, compile_markdown

async def run_pipeline(company: str, locale: str, sections: List[str]):
    resolved_name, seed_urls = await resolve_company(company)
    buckets = await search_buckets(resolved_name)
    urls = list(dict.fromkeys(seed_urls + [u for b in buckets.values() for u in b]))[:40]
    docs = await fetch_and_extract(urls)
    docs = [d for d in docs if d.get("text") and len(d["text"]) > 400]

    briefings = await make_briefings(resolved_name, docs, locale, sections)
    md, sources = await compile_markdown(resolved_name, briefings, docs)

    meta = {"resolved_name": resolved_name, "source_count": len(sources)}
    # ⬇️ теперь отдаём и briefings
    return md, sources, meta, briefings
