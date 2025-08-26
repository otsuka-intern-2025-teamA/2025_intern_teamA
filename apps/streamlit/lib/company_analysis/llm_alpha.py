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

# llm.py に追加
def generate_tavily_queries(company: str, user_input: str = "", max_queries: int = 5) -> List[str]:
    """
    Tavily で使う自然言語クエリを GPT で生成する。
    返り値はクエリ文字列の配列。日本語/英語の両方を混ぜて出して良い。
    """
    s = get_settings()
    client = get_client()

    # モデル名の決定（Azure はデプロイ名必須）
    if s.use_azure:
        model_name = "gpt-5-mini"
        if not model_name:
            raise RuntimeError(
                "Azure利用時は AZURE_OPENAI_CHAT_DEPLOYMENT（デプロイ名）が必要です。"
            )
    else:
        model_name = s.default_model

    sys = (
        "あなたはWebリサーチに最適な検索クエリを作る専門家です。"
        "与えられた会社名と質問から、重複しない 3〜5 個の短い検索クエリを作ってください。"
        "Tavily等の一般Web検索を想定し、次を心がけてください："
        " - 名詞中心で簡潔（10語以内）、余計な助詞は省略"
        " - 日本語と英語の混在も可（固有名詞＋英語の一般語彙）"
        " - 年/期間など具体化（例：2024, 直近1年, market share, product launch）"
        " - 会社名は必ず1つ以上のクエリに含める"
        " - 同義語や関連語（issues, risks, challenges, roadmap, partnership, compliance など）をばらして出す"
        " - 特定の媒体に偏らない（site: 指定は基本避ける）"
        "出力は JSON のみ、キーは queries（文字列配列）だけ。"
    )
    usr = (
        f"会社名: {company}\n"
        f"ユーザー入力/意図: {user_input}\n"
        f"最大クエリ数: {max_queries}\n"
        "フォーマット: {\"queries\": [\"...\"]}"
    )

    try:
        resp = client.chat.completions.create(
            model=model_name,
            messages=[{"role": "system", "content": sys},
                      {"role": "user", "content": usr}],
            response_format={"type": "json_object"},
        )
        content = resp.choices[0].message.content or "{}"
        data = json.loads(content)
        queries = data.get("queries", [])
    except Exception:
        # 失敗時フォールバック：最低限のクエリ
        queries = []

    # 後処理：空・重複を除去、上限数で切る
    cleaned = []
    seen = set()
    for q in queries:
        q = (q or "").strip()
        if not q:
            continue
        if q.lower() in seen:
            continue
        seen.add(q.lower())
        cleaned.append(q)
        if len(cleaned) >= max_queries:
            break

    # それでも空なら素朴に作る
    if not cleaned:
        base = (user_input or "").strip()
        if base:
            cleaned = [f"{company} {base}", f"{company} overview", f"{company} recent news"]
        else:
            cleaned = [f"{company} overview", f"{company} recent news", f"{company} competitors"]

    return cleaned


def company_briefing_with_web_search(company: str, hits: List[SearchHit]) -> CompanyReport:
    s = get_settings()
    client = get_client()

    # モデル名
    if s.use_azure:
        model_name = "gpt-5-mini"
        if not model_name:
            raise RuntimeError("Azure利用時は AZURE_OPENAI_CHAT_DEPLOYMENT（デプロイ名）が必要です。")
    else:
        model_name = s.default_model

    evidence = [
        {
            "title": h.title,
            "url": h.url,
            "snippet": h.snippet,
            "published": h.published or ""
        }
        for h in (hits or [])
    ]

    # JSON構造で返すようにプロンプト設計
    sys = (
        "あなたは入念な企業調査アナリストです。"
        "与えられた証拠(検索ヒット)のみを根拠に日本語で要約してください。"
        "推測は禁止。不明は『公開情報では不明』と明記。日付はYYYY-MM-DD。"
        "出力はJSONのみ。キーは overview, offerings, customers_and_markets, "
        "recent_news, competitors, risks, suggested_questions のみ。"
    )
    usr = (
        f"企業名: {company}\n"
        f"検索結果(証拠): {json.dumps(evidence, ensure_ascii=False)}\n"
        "要件:\n"
        "- 証拠に無い事実は書かない\n"
        "- recent_news は箇条書き形式の文字列でOK（各項目に日付を含める努力）\n"
        "- suggested_questions は3〜5件\n"
        "出力: JSON オブジェクトのみ"
    )

    try:
        # JSONモード
        resp = client.chat.completions.create(
            model=model_name,
            messages=[{"role": "system", "content": sys},
                      {"role": "user", "content": usr}],
            response_format={"type": "json_object"},
        )
        content = resp.choices[0].message.content or "{}"
        data = json.loads(content)
        return CompanyReport(
            company=company,
            overview=data.get("overview", "—"),
            offerings=data.get("offerings", "—"),
            customers_and_markets=data.get("customers_and_markets", "—"),
            recent_news=data.get("recent_news", "—"),
            competitors=data.get("competitors", "—"),
            risks=data.get("risks", "—"),
            suggested_questions=data.get("suggested_questions", []),
            sources=[h.url for h in hits if getattr(h, "url", None)],
        )
    except Exception as e_json:
        # フォールバック（通常生成→パース試行）
        try:
            resp = client.chat.completions.create(
                model=model_name,
                messages=[{"role": "system", "content": sys},
                          {"role": "user", "content": usr}],
            )
            content = resp.choices[0].message.content or ""
            try:
                data = json.loads(content)
                return CompanyReport(
                    company=company,
                    overview=data.get("overview", content or "—"),
                    offerings=data.get("offerings", "—"),
                    customers_and_markets=data.get("customers_and_markets", "—"),
                    recent_news=data.get("recent_news", "—"),
                    competitors=data.get("competitors", "—"),
                    risks=data.get("risks", "—"),
                    suggested_questions=data.get("suggested_questions", []),
                    sources=[h.url for h in hits if getattr(h, "url", None)],
                )
            except json.JSONDecodeError:
                # 生成がJSONでない場合は overview に全文を格納
                return CompanyReport(
                    company=company,
                    overview=content or "LLMの処理中にエラーが発生しました。",
                    offerings="—",
                    customers_and_markets="—",
                    recent_news="—",
                    competitors="—",
                    risks="—",
                    suggested_questions=[],
                    sources=[h.url for h in hits if getattr(h, "url", None)],
                )
        except Exception as e_fallback:
            # 完全失敗
            return CompanyReport(
                company=company,
                overview=f"LLMの処理中にエラーが発生しました: {e_fallback}",
                offerings="—",
                customers_and_markets="—",
                recent_news="—",
                competitors="—",
                risks="—",
                suggested_questions=[],
                sources=[h.url for h in hits if getattr(h, "url", None)],
            )


def company_briefing_without_web_search(company: str, user_input: str) -> CompanyReport:
    s = get_settings()
    client = get_client()

    if s.use_azure:
        model_name = "gpt-5-mini"
        if not model_name:
            raise RuntimeError("Azure利用時は AZURE_OPENAI_CHAT_DEPLOYMENT（デプロイ名）が必要です。")
    else:
        model_name = s.default_model

    sys = (
        "あなたは入念な企業調査アナリストです。"
        "ユーザーの質問に基づき、構造化された企業分析の草案を日本語で返してください。"
        "出力はJSONのみ。キーは overview, offerings, customers_and_markets, "
        "recent_news, competitors, risks, suggested_questions のみ。"
        "不明は『公開情報では不明』と書く。"
    )
    usr = (
        f"企業名: {company}\n"
        f"ユーザーの質問: {user_input}\n"
        "出力: JSON オブジェクトのみ"
    )

    try:
        resp = client.chat.completions.create(
            model=model_name,
            messages=[{"role": "system", "content": sys},
                      {"role": "user", "content": usr}],
            response_format={"type": "json_object"},
        )
        content = resp.choices[0].message.content or "{}"
        data = json.loads(content)
        return CompanyReport(
            company=company,
            overview=data.get("overview", "—"),
            offerings=data.get("offerings", "—"),
            customers_and_markets=data.get("customers_and_markets", "—"),
            recent_news=data.get("recent_news", "—"),
            competitors=data.get("competitors", "—"),
            risks=data.get("risks", "—"),
            suggested_questions=data.get("suggested_questions", []),
            sources=[],
        )
    except Exception as e_json:
        # フォールバック（通常生成→パース試行）
        try:
            resp = client.chat.completions.create(
                model=model_name,
                messages=[{"role": "system", "content": sys},
                          {"role": "user", "content": usr}],
            )
            content = resp.choices[0].message.content or ""
            try:
                data = json.loads(content)
                return CompanyReport(
                    company=company,
                    overview=data.get("overview", content or "—"),
                    offerings=data.get("offerings", "—"),
                    customers_and_markets=data.get("customers_and_markets", "—"),
                    recent_news=data.get("recent_news", "—"),
                    competitors=data.get("competitors", "—"),
                    risks=data.get("risks", "—"),
                    suggested_questions=data.get("suggested_questions", []),
                    sources=[],
                )
            except json.JSONDecodeError:
                return CompanyReport(
                    company=company,
                    overview=content or "LLMの処理中にエラーが発生しました。",
                    offerings="—",
                    customers_and_markets="—",
                    recent_news="—",
                    competitors="—",
                    risks="—",
                    suggested_questions=[],
                    sources=[],
                )
        except Exception as e_fallback:
            return CompanyReport(
                company=company,
                overview=f"LLMの処理中にエラーが発生しました: {e_fallback}",
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
    return company_briefing_with_web_search(company, hits)