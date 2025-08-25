# llm.py
import json
from typing import List
from .data import SearchHit, CompanyReport
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


def company_briefing_with_web_search(company: str, hits: List[SearchHit]) -> CompanyReport:
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

    # 構造化された出力を要求するプロンプト
    messages = [
        {
            "role": "system",
            "content": (
                "あなたは入念な企業調査アナリストです。"
                "与えられた証拠(検索ヒット)“のみ”を根拠に、日本語で厳密に要約します。"
                "推測は禁止。不明は「公開情報では不明」と明記。日付はYYYY-MM-DD。"
                "競合は根拠がある場合のみ。"
                "出力はJSONのみで、次のキー“だけ”を含める: overview, offerings, customers_and_markets, recent_news, competitors, risks, suggested_questions。"
                "recent_newsは箇条書きで各項目に日付と出典URLインデックスを付けること（例: \"2025-03-14: 〇〇 … [#3]\")."
                "suggested_questionsは初回商談で必ず効果のある3〜5問。"
                "以下の要件を必ず守ってください。"
            )
        },
        {
            "role": "user",
            "content": (
                f"企業名: {company}\n"
                f"検索結果(証拠): {json.dumps(evidence, ensure_ascii=False)}\n"
                "要件:\n"
                "- 証拠に存在しない事実は書かない\n"
                "- 相反情報は“両説”と日付を併記し、より新しい方に注釈(例:『※新しい』)\n"
                "- offeringsは製品/サービス分類で簡潔に\n"
                "- customers_and_marketsは主要顧客タイプ/チャネル/地域\n"
                "- risksは導入障壁(稟議/セキュリティ/法令/季節性/依存)の観点\n"
                "- suggested_questionsは初回商談で必ず効果のある3〜5問\n"
                "出力フォーマット:\n"
                "{\n"
                "  \"overview\": \"…\",\n"
                "  \"offerings\": \"…\",\n"
            )
        }
    ]

    try:
        # JSONモードを試行
        resp = client.chat.completions.create(
            model=model_name,
            messages=messages,
            response_format={"type": "json_object"},
        )
    except Exception as e:
        # JSONモードが失敗した場合のフォールバック
        print(f"JSON mode failed: {e}")
        try:
            resp = client.chat.completions.create(
                model=model_name,
                messages=messages,
            )
        except Exception as e2:
            print(f"Fallback also failed: {e2}")
            # 完全に失敗した場合のデフォルトレスポンス
            return CompanyReport(
                company=company,
                overview="LLMの処理中にエラーが発生しました。",
                offerings="—",
                customers_and_markets="—",
                recent_news="—",
                competitors="—",
                risks="—",
                suggested_questions=[],
                sources=[h.url for h in hits if h.url] if hits else [],
            )

    content = resp.choices[0].message.content or ""
    
    # JSONレスポンスをパース
    try:
        if content.strip().startswith("{"):
            parsed = json.loads(content)
            return CompanyReport(
                company=company,
                overview=parsed.get("overview", "—"),
                offerings=parsed.get("offerings", "—"),
                customers_and_markets=parsed.get("customers_and_markets", "—"),
                recent_news=parsed.get("recent_news", "—"),
                competitors=parsed.get("competitors", "—"),
                risks=parsed.get("risks", "—"),
                suggested_questions=parsed.get("suggested_questions", []),
                sources=[h.url for h in hits if h.url] if hits else [],
            )
        else:
            # JSONでない場合のフォールバック処理
            return CompanyReport(
                company=company,
                overview=content,
                offerings="—",
                customers_and_markets="—",
                recent_news="—",
                competitors="—",
                risks="—",
                suggested_questions=[],
                sources=[h.url for h in hits if h.url] if hits else [],
            )
    except json.JSONDecodeError:
        # JSONパースに失敗した場合のフォールバック
        return CompanyReport(
            company=company,
            overview=content,
            offerings="—",
            customers_and_markets="—",
            recent_news="—",
            competitors="—",
            risks="—",
            suggested_questions=[],
            sources=[h.url for h in hits if h.url] if hits else [],
        )


def company_briefing_without_web_search(company: str, user_input: str) -> CompanyReport:
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

    # 構造化された出力を要求するプロンプト
    messages = [
        {
            "role": "system",
            "content": (
                "あなたは入念な企業調査アナリストです。"
                "ユーザーからの質問や要望に基づいて、"
                "企業分析に関するアドバイスを提供してください。"
                "以下のJSON形式で回答してください。"
                "各フィールドは日本語で具体的に記述し、"
                "不明な場合は「公開情報では不明」と記載してください。"
                "JSONの形式は必ず守ってください。"
            )
        },
        {
            "role": "user",
            "content": (
                f"企業名: {company}\n"
                f"ユーザーの質問・要望: {user_input}\n\n"
                "以下のJSON形式で企業分析結果を出力してください：\n"
                "{\n"
                '  "overview": "企業の概要・特徴",\n'
                '  "offerings": "提供している製品・サービス",\n'
                '  "customers_and_markets": "顧客・市場",\n'
                '  "recent_news": "直近のニュース・動向",\n'
                '  "competitors": "競合",\n'
                '  "risks": "リスク・留意点",\n'
                '  "suggested_questions": ["質問1", "質問2"]\n'
                "}"
            )
        }
    ]

    try:
        # JSONモードを試行
        resp = client.chat.completions.create(
            model=model_name,
            messages=messages,
            response_format={"type": "json_object"},
        )
    except Exception as e:
        # JSONモードが失敗した場合のフォールバック
        print(f"JSON mode failed: {e}")
        try:
            resp = client.chat.completions.create(
                model=model_name,
                messages=messages,
            )
        except Exception as e2:
            print(f"Fallback also failed: {e2}")
            # 完全に失敗した場合のデフォルトレスポンス
            return CompanyReport(
                company=company,
                overview="LLMの処理中にエラーが発生しました。",
                offerings="—",
                customers_and_markets="—",
                recent_news="—",
                competitors="—",
                risks="—",
                suggested_questions=[],
                sources=[],
            )

    content = resp.choices[0].message.content or ""
    
    # JSONレスポンスをパース
    try:
        if content.strip().startswith("{"):
            parsed = json.loads(content)
            return CompanyReport(
                company=company,
                overview=parsed.get("overview", "—"),
                offerings=parsed.get("offerings", "—"),
                customers_and_markets=parsed.get("customers_and_markets", "—"),
                recent_news=parsed.get("recent_news", "—"),
                competitors=parsed.get("competitors", "—"),
                risks=parsed.get("risks", "—"),
                suggested_questions=parsed.get("suggested_questions", []),
                sources=[],
            )
        else:
            # JSONでない場合のフォールバック処理
            return CompanyReport(
                company=company,
                overview=content,
                offerings="—",
                customers_and_markets="—",
                recent_news="—",
                competitors="—",
                risks="—",
                suggested_questions=[],
                sources=[],
            )
    except json.JSONDecodeError:
        # JSONパースに失敗した場合のフォールバック
        return CompanyReport(
            company=company,
            overview=content,
            offerings="—",
            customers_and_markets="—",
            recent_news="—",
            competitors="—",
            risks="—",
            suggested_questions=[],
            sources=[],
        )


# 後方互換性のため既存の関数名も保持
def company_briefing(company: str, hits: List[SearchHit]) -> CompanyReport:
    """後方互換性のための関数（company_briefing_with_web_searchと同じ）"""
    return company_briefing_with_web_search(company, hits)
