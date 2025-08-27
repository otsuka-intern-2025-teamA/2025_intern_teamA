import json

# ▼ 追加：Universal Context を常時前置する
from apps.shared.prompting.universal_context import build_uc_for_company_analysis_full
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


def _prepend_uc_messages(company: str, base_messages: list[dict], *,
                         sales_objective: str | None = None,
                         audience: str | None = None) -> list[dict]:
    """
    Universal Context（営業ドクトリン／4層フレーム／情報源／アクティベーション＋ガードレール）を
    System 先頭に 1 件だけ差し込む。出力フォーマットは縛らない。
    """
    uc = build_uc_for_company_analysis_full(
        company,
        sales_objective=sales_objective,
        audience=audience,
    )
    if uc and uc.strip():
        return [{"role": "system", "content": uc}] + base_messages
    return base_messages


# 自然言語クエリを生成
def generate_tavily_queries(
    company: str,
    user_input: str = "",
    max_queries: int = 5,
    *,
    sales_objective: str | None = None,
    audience: str | None = None,
) -> list[str]:
    """
    ちょうど max_queries 個の検索クエリを返す（不足分は自動補完）。
    - UC を System 先頭に前置
    - JSON {"queries": [...]} を強制
    - 再現性のため temperature を下げる
    """
    s = get_settings()
    client = get_client()
    model_name = "gpt-5-mini" if s.use_azure else s.default_model

    # LLM への明示指示：必ず "ちょうど" N 件
    sys = (
        "あなたはWebリサーチに最適な検索クエリを作る専門家です。"
        f"与えられた会社名と質問から、重複しない ちょうど {max_queries} 個 の短い検索クエリを作ってください。"
        "一般Web検索（Tavily/Bing等）を想定し、次を心がけてください："
        " - 名詞中心で簡潔（10語以内）"
        " - 日本語と英語の混在を許容（固有名詞＋一般語彙）"
        " - 年/期間を具体化（例：2024, FY2024, 2024-Q4, market share）"
        " - 会社名は複数のクエリに含める（少なくとも半数）"
        " - 同義語や関連語（issues, risks, roadmap, partnership, compliance など）を分散"
        " - 必要に応じて site: 指定を使ってよい（IR/EDINET/go.jp/PR/LinkedIn 等）"
        "出力は JSON のみ、キーは queries（文字列配列）だけ。"
        f'例: {{"queries": ["{company} 有価証券報告書 2024", "{company} 中期経営計画 DX 2025", "..."]}}'
    )
    usr = (
        f"会社名: {company}\n"
        f"ユーザー入力/意図: {user_input}\n"
        f"必要なクエリ数: {max_queries}\n"
        'フォーマット: {"queries": ["..."]}（配列長は必ず上記の件数に一致させる）'
    )

    # UC を最初の System として前置
    messages = _prepend_uc_messages(
        company,
        base_messages=[
            {"role": "system", "content": sys},
            {"role": "user", "content": usr},
        ],
        sales_objective=sales_objective,
        audience=audience,
    )

    queries: list[str] = []
    try:
        resp = client.chat.completions.create(
            model=model_name,
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0.2,
        )
        content = resp.choices[0].message.content or "{}"
        data = json.loads(content)
        queries = data.get("queries", []) or []
    except Exception:
        queries = []

    # 正規化（空/重複/トリム）
    cleaned: list[str] = []
    seen: set[str] = set()
    for q in queries:
        q = (q or "").strip()
        if not q:
            continue
        key = q.lower()
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(q)

    # ----- 不足分は営業向け“定番スロット”で自動補完 → ちょうど N 件に -----
    def _auto_fill(company: str, intent: str, need: int) -> list[str]:
        base = (intent or "overview").strip()
        # 優先ソースを含むテンプレを多めに用意（site: は検索エンジン側で無視されても無害）
        slots = [
            f"{company} 決算短信 2024 OR 2025",
            f"{company} 有価証券報告書 site:disclosure.edinet-fsa.go.jp",
            f"{company} 中期経営計画 DX",
            f"{company} 役員 組織図",
            f"{company} 人事 異動 2024",
            f"{company} 採用 募集職種 OR 採用情報",
            f"{company} LinkedIn",
            f"{company} 業務提携 OR 資本業務提携 OR M&A",
            f"{company} プレスリリース site:prtimes.jp",
            f"{company} 規制 動向 site:go.jp",
            f"{company} 導入事例 OR 事例",
            f"{company} {base} market share",
            f"{company} 競合 比較 2024",
        ]
        out = []
        for cand in slots:
            if len(out) >= need:
                break
            if cand.lower() in seen:
                continue
            seen.add(cand.lower())
            out.append(cand)
        # それでも足りなければ素朴に埋める
        while len(out) < need:
            extra = f"{company} {base} extra-{len(out)+1}"
            if extra.lower() in seen:
                break
            seen.add(extra.lower())
            out.append(extra)
        return out

    if len(cleaned) < max_queries:
        cleaned.extend(_auto_fill(company, user_input, max_queries - len(cleaned)))

    # 多すぎたら切り詰め
    if len(cleaned) > max_queries:
        cleaned = cleaned[:max_queries]

    return cleaned



def company_briefing_with_web_search(
    company: str,
    hits: list[SearchHit],
    context: str = "",
    *,
    sales_objective: str | None = None,
    audience: str | None = None,
) -> str:
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

    base_messages = [
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

    # ▼ Universal Context を System 先頭に追加
    messages = _prepend_uc_messages(
        company,
        base_messages=base_messages,
        sales_objective=sales_objective,
        audience=audience,
    )

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


def company_briefing_without_web_search(
    company: str,
    user_input: str,
    context: str = "",
    *,
    sales_objective: str | None = None,
    audience: str | None = None,
) -> str:
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

    base_messages = [
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

    # ▼ Universal Context を System 先頭に追加
    messages = _prepend_uc_messages(
        company,
        base_messages=base_messages,
        sales_objective=sales_objective,
        audience=audience,
    )

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
