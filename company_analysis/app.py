
import os, requests, json
import streamlit as st
from typing import List
from config import get_settings
from data import SearchHit
from llm import company_briefing
from ui import render_report

st.set_page_config(page_title="Company Intel Bot", page_icon="🔎", layout="wide")

@st.cache_data(show_spinner=False)
def bing_search(query: str, count: int = 6, freshness: str = "Month") -> List[SearchHit]:
    """Simple Bing Web Search wrapper (web pages + news)."""
    settings = get_settings()
    key = settings.bing_search_key
    hits: List[SearchHit] = []
    if not key:
        return hits

    headers = {"Ocp-Apim-Subscription-Key": key}
    params = {"q": query, "mkt": "ja-JP", "count": count, "freshness": freshness, "textDecorations": False}

    # Web search
    r = requests.get("https://api.bing.microsoft.com/v7.0/search", headers=headers, params=params, timeout=15)
    if r.status_code == 200:
        data = r.json()
        for item in (data.get("webPages", {}) or {}).get("value", []):
            hits.append(SearchHit(
                title=item.get("name", ""),
                url=item.get("url", ""),
                snippet=item.get("snippet", ""),
                published=None
            ))

    # News search (optional add)
    rn = requests.get("https://api.bing.microsoft.com/v7.0/news/search", headers=headers,
                      params={"q": query, "mkt": "ja-JP", "count": 6, "freshness": freshness}, timeout=15)
    if rn.status_code == 200:
        data = rn.json()
        for item in data.get("value", []):
            date_p = item.get("datePublished", "")
            url = (item.get("url") or "")
            title = item.get("name", "")
            snippet = item.get("description", "")
            hits.append(SearchHit(title=title, url=url, snippet=snippet, published=date_p))

    # Deduplicate by URL
    seen = set()
    uniq = []
    for h in hits:
        if h.url and h.url not in seen:
            seen.add(h.url)
            uniq.append(h)
    return uniq[: max(count, 6)]

@st.cache_data(show_spinner=False)
def tavily_search(query: str, count: int = 6) -> List[SearchHit]:
    """
    Tavily search fallback (if BING_SEARCH_KEY is not set). Requires TAVILY_API_KEY in env.
    """
    settings = get_settings()
    key = settings.tavily_api_key
    hits: List[SearchHit] = []
    if not key:
        return hits

    r = requests.post(
        "https://api.tavily.com/search",
        headers={"Content-Type": "application/json"},
        json={"api_key": key, "query": query, "max_results": count, "include_answer": False, "search_depth": "advanced"},
        timeout=20
    )
    if r.status_code == 200:
        data = r.json()
        for item in data.get("results", []):
            hits.append(SearchHit(
                title=item.get("title", ""),
                url=item.get("url", ""),
                snippet=item.get("content", ""),
                published=item.get("published_date")
            ))
    return hits

def run_search(query: str, count: int = 8, freshness: str = "Month") -> List[SearchHit]:
    hits = bing_search(query, count=count, freshness=freshness)
    if not hits:
        hits = tavily_search(query, count=count)
    return hits

def main():
    st.title("🔎 企業インテリジェンス（LLM要約）")
    st.write("会社名を入力すると、公開Web情報からLLMが日本語でブリーフィングを作成します。")

    with st.sidebar:
        st.header("設定")
        st.caption("環境変数は .env で設定できます。")
        col1, col2 = st.columns(2)
        with col1:
            top_k = st.number_input("検索結果件数", 4, 20, 8, 1)
        with col2:
            freshness = st.selectbox("ニュースの鮮度", ["Day", "Week", "Month"], index=2)

    company = st.text_input("企業名（例: 大塚商会、楽天グループ、ソニーグループ）")
    run = st.button("調べる")

    if run and company.strip():
        st.info("検索中…")
        hits = run_search(company.strip(), count=int(top_k), freshness=freshness)

        if not hits:
            st.error("検索結果が見つかりませんでした。BING_SEARCH_KEY または TAVILY_API_KEY を設定してください。")
            return

        st.success(f"検索ヒット: {len(hits)} 件")
        with st.expander("根拠（検索スニペット）を見る", expanded=False):
            for h in hits:
                pub = f"（{h.published}）" if h.published else ""
                st.markdown(f"- **{h.title}** {pub}\n  \n  {h.snippet}\n  \n  {h.url}")

        with st.spinner("LLMで要約中…"):
            report = company_briefing(company.strip(), hits)

        render_report(report)

if __name__ == "__main__":
    main()
