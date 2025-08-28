import json
from typing import Any, List, Optional

# ▼ Universal Context（前置）: パス差異に強いtry-import
try:
    from .universal_context import build_uc_for_company_analysis_full
except Exception:  # pragma: no cover
    try:
        from apps.shared.prompting.universal_context import build_uc_for_company_analysis_full
    except Exception:
        from universal_context import build_uc_for_company_analysis_full  # 最後の手段

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


# ==============
# 新規: ユーザー意図抽出
# ==============
def extract_user_intent(company: str, user_input: str, chat_history: str = "") -> dict:
    """
    直近の質問と簡易履歴から、意思決定に必要な意図をJSONで構造化抽出。
    出力:
      {"goal":"","decision":"","constraints":[],"timeframe":"",
       "kpis":[],"entities":[],"query_seed":""}
    """
    s = get_settings()
    client = get_client()
    model_name = "gpt-5-mini" if s.use_azure else s.default_model

    sys = (
        "あなたはB2B営業の要件定義アナリストです。"
        "ユーザーの直近メッセージ（と任意のチャット履歴）から、"
        "意思決定に必要な『意図の要約』をJSONで構造化してください。"
        "推測は避け、不明はnullに。日本語。"
        '出力は必ずJSON: {"goal":"","decision":"","constraints":[],"timeframe":"","kpis":[],"entities":[],"query_seed":""}'
    )
    usr = (
        f"会社名: {company}\n"
        f"ユーザー入力: {user_input}\n"
        f"チャット履歴要約(任意): {chat_history}\n"
        "上記から、ユーザーが考えていると思われる最も重要な目的/判断したいこと/主要トピックを抽出し、"
        "検索用に短いquery_seed（10語以内、名詞中心）も作ってください。"
    )

    messages = _prepend_uc_messages(  # UC前置
        company,
        base_messages=[{"role": "system", "content": sys}, {"role": "user", "content": usr}],
        sales_objective=None, audience=None
    )
    try:
        resp = client.chat.completions.create(
            model=model_name,
            messages=messages,
            response_format={"type": "json_object"},
            # temperature=0.2,
        )
        content = resp.choices[0].message.content or "{}"
        return json.loads(content)
    except Exception as e:
        print(f"[extract_user_intent] error: {e}")  # ← 原因が見える
        return _intent_fallback(user_input) 

def _intent_fallback(text: str) -> dict:
    import re
    # ざっくり年月(例: 2025年3月) を拾う
    m = re.search(r"(20\\d{2})年\\s*(\\d{1,2})月", text)
    timeframe = f"{m.group(1)}年{m.group(2)}月" if m else None
    # 名詞中心の軽いseed（空白区切り→先頭10語）
    seed = " ".join(re.findall(r"[\\w\\u3040-\\u30FF\\u4E00-\\u9FFF]+", text))[:80]
    return {"goal": None, "decision": None, "constraints": [], "timeframe": timeframe,
            "kpis": [], "entities": [], "query_seed": seed or None}

# 自然言語クエリを生成（既存強化：ちょうどN件）
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

    sys = (
        "あなたはWebリサーチ用の検索クエリを作る専門家です。"
        f"与えられた会社名と質問から、重複しない ちょうど {max_queries} 個 の検索クエリを作成します。"
        "出力要件：\n"
        " - 各クエリは “単語列”ではなく “検索フレーズ”（3〜10語、スペース区切り）\n"
        " - 各クエリには次のうち少なくとも2要素を含める：{会社名}/{時間軸（年・月・四半期）}/{話題・情報源（例: プレスリリース, 決算短信, 有価証券報告書, 人事 異動, 導入事例, market share, site:prtimes.jp, site:go.jp など）}\n"
        " - 会社名は半数以上のクエリに含める\n"
        " - 同義反復は避け、言い換えや情報源を分散\n"
        " - 日本語主体でよいが、固有名詞や一般語の英語も許容（例: market share, partnership）\n"
        " - 出力は JSON のみ、キーは queries（文字列配列）だけ。配列長は必ず指定件数に一致\n"
        f'例: {{"queries": ["{company} 2024年4月 プレスリリース site:prtimes.jp", "{company} 決算短信 2024", "..."]}}'
    )
    usr = (
        f"会社名: {company}\n"
        f"ユーザー入力/意図: {user_input}\n"
        f"必要なクエリ数: {max_queries}\n"
        'フォーマット: {"queries": ["..."]}（配列長は必ず上記の件数に一致させる）'
    )

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

    # 正規化
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

    if len(cleaned) > max_queries:
        cleaned = cleaned[:max_queries]

    return cleaned


def company_briefing_with_web_search(
    company: str,
    hits: List[SearchHit],
    context: str = "",
    *,
    sales_objective: Optional[str] = None,
    audience: Optional[str] = None,
) -> str:
    """Web検索結果を使用した企業分析（役割/手順を明示。最後に参考リンク必須）"""
    s = get_settings()
    client = get_client()
    model_name = "gpt-5-mini" if s.use_azure else s.default_model

    evidence = [
        {"title": h.title, "url": h.url, "snippet": h.snippet, "published": h.published or ""} for h in (hits or [])
    ]

    base_messages = [
        {
            "role": "system",
            "content": (
                "あなたはB2B企業調査アナリストです。"
                "【役割】ユーザー意図に合致する“意思決定可能な結論”を、最新のWeb証拠に基づき提示し、"
                "残る不確実性を3つの検証質問へ落とし込む。"
                "【目的】(1) 直問の結論 (2) 主要根拠(日付/数値/出典) (3) 重要洞察と含意 (4) リスク/不明点の明確化 (5) 次アクション設計。"
                "【制約】証拠第一。推測しない。相反は『両説＋日付』を併記し新しい方に『※新しい』。抽象語の濫用禁止。日本語。"
                "【フォーマット】必ずMarkdownで出力。セクション見出しは`##`、小見出しは`###`、ラベルは**太字:**（例: **目的:**）。箇条書きは`-`で始める。"
                "Markdownが使えない環境と判断したら同じ構成で見出しを【…】で囲む。"
                "【手順】Step1: 入力の『ユーザー意図(目的/判断/期間/KPI)』を先頭1〜3行で要約。"
                "Step2: 証拠を照合して結論→根拠→洞察→リスク/不明点。"
                "Step3: 次質問3件（後述仕様）。"
                "【出力】見出し＋箇条書きで簡潔。末尾は必ず『参考リンク』。"
            ),
        },
        {
            "role": "user",
            "content": (
                f"企業名: {company}\n"
                f"検索結果(証拠): {json.dumps(evidence, ensure_ascii=False)}\n"
                f"{context if context else ''}\n"
                "要件:\n"
                "- 証拠に存在しない事実は書かない（推測禁止）。\n"
                "- 相反情報は『両説＋日付』を併記し、新しい方に『※新しい』。\n"
                "- まず『ユーザー意図の要約』→その後に本文（結論/根拠/洞察/リスク）。\n"
                "- 『参考リンク』の直前に『## 次に聞くべき質問（例）』を**ちょうど3件**列挙：\n"
                "  ルール: 各質問は1–2文で、必ず〔数値/期間/対象部署or役職/判断基準〕を含める。抽象語だけは禁止。\n"
                "  併記情報: (意図:10語以内) (対象:役職or部署) (根拠: どのURL/出典に基づくか) (次アクション:Yes/No時の一言)。\n"
                "- 最後に『参考リンク』節（採用したURLを列挙）。\n"
            ),
        },
    ]

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
    sales_objective: Optional[str] = None,
    audience: Optional[str] = None,
) -> str:
    """Web検索なし（与えられた入力のみで結論→3質問まで導出）"""
    s = get_settings()
    client = get_client()
    model_name = "gpt-5-mini" if s.use_azure else s.default_model

    base_messages = [
        {
            "role": "system",
            "content": (
                "あなたはB2B企業調査アナリストです。"
                "【役割】ユーザー意図に合致する“意思決定可能な結論”を、与えられた入力のみで提示し、"
                "残る不確実性を3つの検証質問へ落とし込む。"
                "【目的】(1) 直問の結論 (2) 主要根拠（本文内で明示） (3) 重要洞察と含意 (4) 不明点の明確化 (5) 次アクション設計。"
                "【制約】推測は避け、不明は不明と明記。相反は『両説＋日付』で整理。日本語。"
                "【フォーマット】必ずMarkdownで出力。セクション見出しは`##`、小見出しは`###`、ラベルは**太字:**（例: **目的:**）。箇条書きは`-`で始める。"
                "Markdownが使えない環境と判断したら同じ構成で見出しを【…】で囲む。"
                "【手順】Step1: 入力の『ユーザー意図(目的/判断/期間/KPI)』を先頭1〜3行で要約。"
                "Step2: 結論→根拠→洞察→不明点。Step3: 次質問3件（仕様下記）。"
                "【出力】見出し＋箇条書き中心。末尾の参考リンクは任意。"
            ),
        },
        {
            "role": "user",
            "content": (
                f"企業名: {company}\n"
                f"ユーザーの質問・要望: {user_input}\n"
                f"{context if context else ''}\n\n"
                "要件:\n"
                "- まず『ユーザー意図の要約』→その後に本文（結論/根拠/洞察/不明点）。\n"
                "- 出力末尾付近に『## 次に聞くべき質問（例）』を**ちょうど3件**：\n"
                "  ルール: 各質問は1–2文で、必ず〔数値/期間/対象部署or役職/判断基準〕を含める。抽象語のみは禁止。\n"
                "  併記情報: (意図:10語以内) (対象:役職or部署) (根拠: 本文のどの仮説/記述に基づくか) (次アクション:Yes/No一言)。\n"
            ),
        },
    ]

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


# 後方互換名
def company_briefing(company: str, hits: List[SearchHit], context: str = "") -> str:
    return company_briefing_with_web_search(company, hits, context)
