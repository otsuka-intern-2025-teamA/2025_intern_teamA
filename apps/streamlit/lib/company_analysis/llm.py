# llm.py
import json

from openai import AzureOpenAI, OpenAI

from .config import get_settings
from .data import SearchHit


def get_client():
    s = get_settings()
    if s.use_azure:
        return AzureOpenAI(
            api_version=s.api_version,
            azure_endpoint=s.azure_endpoint,
            api_key=s.azure_api_key,
        )
    return OpenAI(api_key=s.openai_api_key)


# 自然言語クエリを生成
def generate_tavily_queries(company: str, user_input: str = "", max_queries: int = 5) -> list[str]:
    s = get_settings()
    client = get_client()

    if s.use_azure:
        model_name = "gpt-5-mini"
        if not model_name:
            raise RuntimeError("Azure利用時は AZURE_OPENAI_CHAT_DEPLOYMENT（デプロイ名）が必要です。")
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
        'フォーマット: {"queries": ["..."]}'
    )

    try:
        resp = client.chat.completions.create(
            model=model_name,
            messages=[{"role": "system", "content": sys}, {"role": "user", "content": usr}],
            response_format={"type": "json_object"},
        )
        content = resp.choices[0].message.content or "{}"
        data = json.loads(content)
        queries = data.get("queries", [])
    except Exception:
        # 失敗時フォールバック:最低限のクエリ
        queries = []

    # 後処理:空・重複を除去、上限数で切る
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

    print("=== Cleaned queries (final) ===")
    print(cleaned)
    return cleaned


def company_briefing_with_web_search(company: str, hits: list[SearchHit], context: str = "") -> str:
    """Web検索結果を使用した企業分析（柔軟構成／固定テンプレ外し／参考リンクは最後に必ず付与）"""
    s = get_settings()
    client = get_client()

    # Azureは"デプロイ名"が必須
    if s.use_azure:
        model_name = "gpt-5-mini"
        if not model_name:
            raise RuntimeError("Azure利用時は AZURE_OPENAI_CHAT_DEPLOYMENT（デプロイ名）が必要です。")
    else:
        model_name = s.default_model

    # 参考情報（証拠）
    evidence = [
        {"title": h.title, "url": h.url, "snippet": h.snippet, "published": h.published or ""} for h in (hits or [])
    ]

    messages = [
        {
            "role": "system",
            "content": (
                "あなたは入念な企業調査アナリストです。"
                "与えられた証拠（検索ヒット）に厳密に基づき、日本語で回答します。"
                "推測は禁止。不明は「公開情報では不明」と明記。"
                "出力のアウトラインはユーザーの直近の質問意図を最優先し、"
                "必要な場合のみ適切な小見出しを付けてください。"
                "特定の固定テンプレート（例：企業概要/製品/顧客/競合/リスク…）を必須にしないでください。"
                "読みやすいマークダウンで、要点は箇条書きを積極的に用いて簡潔に。"
                "論拠が分かるよう、最後に「参考リンク」を必ず付けてください。"
            ),
        },
        {
            "role": "user",
            "content": (
                f"企業名: {company}\n"
                f"検索結果(証拠): {json.dumps(evidence, ensure_ascii=False)}\n"
                f"{context if context else ''}\n"
                "要件:\n"
                "- 証拠に存在しない事実は書かない（推測禁止）\n"
                "- 相反情報は「両説」と日付を併記し、より新しい方に『※新しい』と注記\n"
                "- ユーザーの質問に直接答える構成を最優先（固定の章立てを強制しない）\n"
                "- 読みやすいマークダウンで簡潔に\n"
                "- 最後に「参考リンク」節を付ける（自動でリンクを追記することがあります）"
            ),
        },
    ]

    try:
        resp = client.chat.completions.create(
            model=model_name,
            messages=messages,
        )
        content = resp.choices[0].message.content or ""
    except Exception as e:
        print(f"LLM処理中にエラーが発生: {e}")
        content = f"# {company} 企業分析\n\nLLMの処理中にエラーが発生しました。\n"
    return content


def company_briefing_without_web_search(company: str, user_input: str, context: str = "") -> str:
    """Web検索なしでユーザー入力のみを使用した企業分析（従来どおり）"""
    s = get_settings()
    client = get_client()

    # Azureは"デプロイ名"が必須
    if s.use_azure:
        model_name = "gpt-5-mini"
        if not model_name:
            raise RuntimeError("Azure利用時は AZURE_OPENAI_CHAT_DEPLOYMENT（デプロイ名）が必要です。")
    else:
        model_name = s.default_model

    messages = [
        {
            "role": "system",
            "content": (
                "あなたは入念な企業調査アナリストです。"
                "ユーザーからの質問や要望に基づいて、企業分析に関するアドバイスを提供してください。"
                "出力は読みやすいマークダウン形式で、ユーザーの質問に直接回答し、"
                "必要に応じて小見出しを付けてください。"
            ),
        },
        {
            "role": "user",
            "content": (
                f"企業名: {company}\n"
                f"ユーザーの質問・要望: {user_input}\n"
                f"{context if context else ''}\n\n"
                "上記の質問・要望に基づいて、企業分析に関するアドバイスをマークダウン形式で出力してください。"
            ),
        },
    ]

    try:
        resp = client.chat.completions.create(
            model=model_name,
            messages=messages,
        )
        content = resp.choices[0].message.content or ""
    except Exception as e:
        print(f"LLM処理中にエラーが発生: {e}")
        content = f"# {company} 企業分析\n\nLLMの処理中にエラーが発生しました。\n\nユーザーの質問: {user_input}"

    return content


# 後方互換性のため既存の関数名も保持
def company_briefing(company: str, hits: list[SearchHit], context: str = "") -> str:
    """後方互換性のための関数(company_briefing_with_web_searchと同じ)"""
    return company_briefing_with_web_search(company, hits, context)
