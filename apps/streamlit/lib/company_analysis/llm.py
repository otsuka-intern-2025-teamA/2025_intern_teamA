# llm.py
import json
from typing import List
from .data import SearchHit
from .config import get_settings
from openai import OpenAI, AzureOpenAI


def get_client():
    s = get_settings()
    if s.use_azure:
        return AzureOpenAI(
            api_version=s.api_version,
            azure_endpoint=s.azure_endpoint,
            api_key=s.azure_api_key,
        )
    return OpenAI(api_key=s.openai_api_key)


def company_briefing_with_web_search(company: str, hits: List[SearchHit]) -> str:
    """Web検索結果を使用した企業分析"""
    s = get_settings()
    client = get_client()

    # Azureは"デプロイ名"が必須
    if s.use_azure:
        model_name = "gpt-5-mini"
        if not model_name:
            raise RuntimeError(
                "Azure利用時は AZURE_OPENAI_CHAT_DEPLOYMENT"
                "（デプロイ名）が必要です。"
            )
    else:
        model_name = s.default_model

    # 参考情報を軽くまとめる（検索なし運用でも空でOK）
    evidence = [
        {
            "title": h.title,
            "url": h.url,
            "snippet": h.snippet,
            "published": h.published or ""
        }
        for h in (hits or [])
    ]

    # マークダウン形式での出力を要求するプロンプト
    messages = [
        {
            "role": "system",
            "content": (
                "あなたは入念な企業調査アナリストです。"
                "与えられた証拠(検索ヒット)のみを根拠に、"
                "日本語で厳密に要約します。"
                "推測は禁止。不明は「公開情報では不明」と明記。"
                "出力は読みやすいマークダウン形式で、"
                "以下のセクションを含めてください：\n"
                "## 企業概要\n"
                "## 提供している製品・サービス\n"
                "## 顧客・市場\n"
                "## 直近のニュース・動向\n"
                "## 競合\n"
                "## リスク・留意点\n"
                "## 次回打ち合わせでの質問案\n"
                "## 参考リンク\n\n"
                "各セクションは具体的で実用的な内容にしてください。"
            )
        },
        {
            "role": "user",
            "content": (
                f"企業名: {company}\n"
                f"検索結果(証拠): {json.dumps(evidence, ensure_ascii=False)}\n"
                "要件:\n"
                "- 証拠に存在しない事実は書かない\n"
                "- 相反情報は「両説」と日付を併記し、"
                "より新しい方に注釈(例:『※新しい』)\n"
                "- 各セクションは簡潔で実用的な内容に\n"
                "- 質問案は初回商談で必ず効果のある3〜5問\n"
                "- マークダウン形式で読みやすく出力"
            )
        }
    ]

    try:
        resp = client.chat.completions.create(
            model=model_name,
            messages=messages,
        )
    except Exception as e:
        print(f"LLM処理中にエラーが発生: {e}")
        error_msg = (
            f"# {company} 企業分析\n\n"
            f"LLMの処理中にエラーが発生しました。\n\n"
            f"## 参考リンク\n"
        )
        links = "\n".join(
            [f"- {h.url}" for h in hits if h.url] if hits else []
        )
        return error_msg + links

    content = resp.choices[0].message.content or ""
    return content


def company_briefing_without_web_search(company: str, user_input: str) -> str:
    """Web検索なしでユーザー入力のみを使用した企業分析"""
    s = get_settings()
    client = get_client()

    # Azureは"デプロイ名"が必須
    if s.use_azure:
        model_name = "gpt-5-mini"
        if not model_name:
            raise RuntimeError(
                "Azure利用時は AZURE_OPENAI_CHAT_DEPLOYMENT"
                "（デプロイ名）が必要です。"
            )
    else:
        model_name = s.default_model

    # マークダウン形式での出力を要求するプロンプト
    messages = [
        {
            "role": "system",
            "content": (
                "あなたは入念な企業調査アナリストです。"
                "ユーザーからの質問や要望に基づいて、"
                "企業分析に関するアドバイスを提供してください。"
                "出力は読みやすいマークダウン形式で、"
                "ユーザーの質問に直接回答し、"
                "必要に応じて以下のセクションを含めてください：\n"
                "## 分析結果\n"
                "## 推奨事項\n"
                "## 次回打ち合わせでの質問案\n\n"
                "各セクションは具体的で実用的な内容にしてください。"
            )
        },
        {
            "role": "user",
            "content": (
                f"企業名: {company}\n"
                f"ユーザーの質問・要望: {user_input}\n\n"
                "上記の質問・要望に基づいて、"
                "企業分析に関するアドバイスをマークダウン形式で出力してください。"
            )
        }
    ]

    try:
        resp = client.chat.completions.create(
            model=model_name,
            messages=messages,
        )
    except Exception as e:
        print(f"LLM処理中にエラーが発生: {e}")
        return (
            f"# {company} 企業分析\n\n"
            f"LLMの処理中にエラーが発生しました。\n\n"
            f"ユーザーの質問: {user_input}"
        )

    content = resp.choices[0].message.content or ""
    return content


# 後方互換性のため既存の関数名も保持
def company_briefing(company: str, hits: List[SearchHit]) -> str:
    """後方互換性のための関数（company_briefing_with_web_searchと同じ）"""
    return company_briefing_with_web_search(company, hits)
