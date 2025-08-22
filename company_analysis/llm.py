# llm.py
import os, json
from typing import List
from data import SearchHit, CompanyReport
from config import get_settings
from openai import OpenAI, AzureOpenAI, APIStatusError

def get_client():
    s = get_settings()
    if s.use_azure:
        return AzureOpenAI(
            api_version=s.api_version,
            azure_endpoint=s.azure_endpoint,
            api_key=s.azure_api_key,
        )
    return OpenAI(api_key=s.openai_api_key)

def company_briefing(company: str, hits: List[SearchHit]) -> CompanyReport:
    s = get_settings()
    client = get_client()

    # Azureは“デプロイ名”が必須
    if s.use_azure:
        model_name = s.azure_chat_deployment
        if not model_name:
            raise RuntimeError("Azure利用時は AZURE_OPENAI_CHAT_DEPLOYMENT（デプロイ名）が必要です。")
    else:
        model_name = s.default_model

    # 参考情報を軽くまとめる（検索なし運用でも空でOK）
    evidence = [
        {"title": h.title, "url": h.url, "snippet": h.snippet, "published": h.published or ""}
        for h in (hits or [])
    ]

    # まずは最小引数で通す
    messages = [
        {"role": "system", "content": (
            "あなたは入念な企業調査アナリストです。"
            "不明点は『公開情報では不明』と書いてください。"
            "事実に忠実に日本語で簡潔に答えてください。"
        )},
        {"role": "user", "content": json.dumps({
            "company": company,
            "evidence": evidence
        }, ensure_ascii=False)}
    ]

    try:
        # 一部デプロイは temperature/top_p 非対応なので渡さない
        resp = client.chat.completions.create(
            model=model_name,
            messages=messages,
            # JSONモードに非対応なデプロイがあるため、まずは付けない
            # response_format={"type": "json_object"},
        )
    except APIStatusError as e:
        # デバッグ出力（必要なら print をコメントアウト）
        print("status:", e.status_code)
        try:
            print("body:", e.response.json())
        except Exception:
            print("body(text):", e.response.text)
        # フォールバック（JSONモード/追加パラメータを一切使わない最小呼び出し）
        resp = client.chat.completions.create(
            model=model_name,
            messages=messages,
        )

    content = resp.choices[0].message.content or ""

    # LLM出力が自由文のときもあるので最低限の形に整形
    return CompanyReport(
        company=company,
        overview=content,
        offerings="",
        customers_and_markets="",
        recent_news="",
        competitors="",
        risks="",
        suggested_questions=[],
        sources=[h.url for h in hits if h.url] if hits else [],
    )
