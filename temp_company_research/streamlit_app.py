# app.py — Company Research Backend 用の Streamlit フロントエンド

import os
import requests
import streamlit as st
from typing import List

from data import CompanyReport
from ui import render_report

# ページ設定
st.set_page_config(page_title="Company Intel", page_icon="🔎", layout="wide")

# --------- 設定 / ENV ----------
BACKEND_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8000").rstrip("/")
DEFAULT_LOCALE = os.getenv("FRONTEND_LOCALE", "ja")  # en | ja | ru
DEFAULT_SECTIONS = ["profile", "products", "market", "financials", "news"]

# llm.company_briefing が更新されていれば利用
_backend_via_llm = None
try:
    from llm import company_briefing as _company_briefing_llm  # type: ignore
    _backend_via_llm = _company_briefing_llm
except Exception:
    _backend_via_llm = None


# --------- 補助関数 ----------
def _call_backend(company: str, locale: str, sections: List[str]) -> CompanyReport:
    """
    FastAPI バックエンド /report を直接呼び出し、CompanyReport にマッピングします。
    """
    url = f"{BACKEND_URL}/report"
    payload = {"company_name": company, "locale": locale, "sections": sections}
    resp = requests.post(url, json=payload, timeout=180)
    if resp.status_code != 200:
        raise RuntimeError(f"Backend error {resp.status_code}: {resp.text}")

    data = resp.json()
    brief = data.get("briefings") or {}
    sources_raw = data.get("sources") or []

    # UI 用にソースを文字列リストへ変換
    sources: List[str] = []
    for s in sources_raw:
        if isinstance(s, dict):
            title = s.get("title") or s.get("url") or ""
            url2 = s.get("url") or ""
            sources.append(f"{title} — {url2}".strip(" —"))
        elif isinstance(s, str):
            sources.append(s)

    overview = brief.get("profile", "")
    offerings = brief.get("products", "")
    market_block = brief.get("market", "")
    financials = brief.get("financials", "")
    news = brief.get("news", "")

    return CompanyReport(
        company=data.get("company") or company,
        overview=overview,
        offerings=offerings,
        customers_and_markets=market_block + (("\n\n" + financials) if financials else ""),
        recent_news=news,
        competitors="",
        risks="",
        suggested_questions=[],
        sources=sources,
    )


def _smart_company_briefing(company: str, locale: str, sections: List[str]) -> CompanyReport:
    """
    汎用レイヤー:
    1) llm.company_briefing(company)（新バージョン）を呼び出し
    2) シグネチャが古い場合（hits を期待）→ 空リストで試行
    3) モジュール/関数がない場合は直接バックエンドへ
    """
    if _backend_via_llm is None:
        return _call_backend(company, locale, sections)

    try:
        # 前ステップの新しいシグネチャ
        return _backend_via_llm(company)  # type: ignore
    except TypeError:
        # 古いバージョン: hits を期待 → 空リストで渡す（互換性のため）
        try:
            return _backend_via_llm(company, [])  # type: ignore
        except Exception:
            # 古い llm が直接 Tavily を呼ぶ場合はスキップしてバックエンドへ
            return _call_backend(company, locale, sections)
    except Exception:
        return _call_backend(company, locale, sections)


# --------- UI ----------
def main():
    st.title("🔎 Company Intel")
    st.caption("フロントは Streamlit、調査は FastAPI バックエンド（Tavily + Azure OpenAI）で動いています。")

    with st.sidebar:
        st.header("設定")
        locale = st.selectbox("言語 / Language", ["ja", "en", "ru"], index=["ja", "en", "ru"].index(DEFAULT_LOCALE))
        st.text_input("Backend URL", BACKEND_URL, key="backend_url_help", disabled=True,
                      help="環境変数 BACKEND_URL で変更できます。")
        st.markdown("---")
        with st.expander("表示するセクション（変更可）", expanded=False):
            selected = []
            for s_name in ["profile", "products", "market", "financials", "news"]:
                checked = st.checkbox(s_name, value=(s_name in DEFAULT_SECTIONS))
                if checked:
                    selected.append(s_name)
        sections = selected or DEFAULT_SECTIONS

    company = st.text_input("企業名（例: 大塚商会、楽天グループ、ソニーグループ）", placeholder="会社名を入力…")
    run = st.button("調べる")

    if run and company.strip():
        with st.spinner("レポート生成中…（数十秒かかることがあります）"):
            try:
                report = _smart_company_briefing(company.strip(), locale, sections)
            except Exception as e:
                st.error(f"エラーが発生しました: {e}")
                st.stop()

        st.success("レポート完成！")
        render_report(report)

    st.markdown("---")
    st.caption(
        f"Backend: `{BACKEND_URL}` ・ エンドポイント: `POST /report` ・ "
        "環境変数: BACKEND_URL / AZURE_OPENAI_* / TAVILY_API_KEY"
    )


if __name__ == "__main__":
    main()
