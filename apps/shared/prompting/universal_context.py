from dataclasses import dataclass
from datetime import datetime


@dataclass
class UniversalContextConfig:
    product_overview: str = (
        "本プロダクトはB2B営業における企業“深掘り”を支援するアシスタント。"
        "目的は、仮説検証の精度向上、対等な関係構築、汎用ピッチから個別提案への変換である。"
    )
    analysis_scope: str = (
        "今回のスコープは『取引先企業そのものの深掘り』。競合分析は別フェーズ。"
        "事実と根拠に基づく内側理解（人・組織／中計・施策／IT・データ／制約・リスク）に集中する。"
    )
    evidence_safety: str = (
        "推測や一般論の水増しを避け、不明は不明と明記。相反情報は年代差・一次情報優先の方針で整理する。"
        "出力形式は固定しないが、冗長を避け簡潔に要点を述べる。"
    )
    # ▶ スタイルのガードレール（新規）
    style_guardrails: str = (
        "【スタイルガード】分析は中立・簡潔・箇条書き重視。"
        "営業アクティベーション（件名/トーク/物語構成）は“必要時のみ参照”とし、"
        "分析テキスト自体を販促口調や物語調に寄せない。"
    )

    language: str = "ja"
    enable: bool = True

    # ▶ すべて既定ON（ユーザー要望）
    include_sales_doctrine: bool = True
    include_research_framework: bool = True
    include_sources_toolkit: bool = True
    include_activation_hints: bool = True

    sales_doctrine: str = (
        "【営業ドクトリン】製品中心の思い込みから顧客中心の洞察へ。初回接触前に業界・市場・潜在課題を徹底把握。"
        "抽象論ではなく具体的な切り口で信頼を獲得。深い知識によりアドバイザー的関係を築き、"
        "価格交渉・異議・導入後課題にも建設的に対処。分析は反対意見の先回り準備と類似事例・客観データ提示を可能にする。"
    )
    research_framework: str = (
        "【4層フレーム】1) マクロ=PEST。2) ミクロ=業界競争・財務推移・中計。"
        "3) 組織/人物=意思決定者と影響者、経歴/発言、採用・文化。"
        "4) 統合と仮説=IRの“公言”と現場の“現実”のギャップを営業機会として具体仮説化。"
    )
    sources_toolkit: str = (
        "【情報源/三角測量】公式サイト・IR・官公庁・業界団体・信用調査・ニュースDB・採用/LinkedIn・展示会/四季報・人脈を組み合わせ、"
        "複数ソース照合で信頼性を高める。最大の機会は“公式と現場のギャップ”に潜む。"
    )
    activation_hints: str = (
        "【営業アクティベーション】アプローチ=『なぜ貴社/なぜ今』を中計/決算に結び付けて明確化。"
        "ヒアリング=SPIN応用（状況→問題→示唆→解決）で具体質問に落とす。"
        "提案=ヒーローズ・ジャーニーでBefore/Afterと実行計画・事例を提示。"
    )

def build_universal_context(
    cfg: UniversalContextConfig,
    *,
    company: str | None = None,
    sales_objective: str | None = None,
    audience: str | None = None,
    profile: str | None = "client_deepdive",
    extra_notes: list[str] | None = None,
    sections: list[str] | None = None,  # 明示指定が最優先
    now: datetime | None = None,
) -> str:
    if not cfg.enable:
        return ""
    now = now or datetime.now()

    header = "[Universal Context]\n"
    core = (
        f"{cfg.product_overview}\n"
        f"{cfg.analysis_scope}\n"
        f"{cfg.evidence_safety}\n"
        f"{cfg.style_guardrails}\n"  # ▶ ガードレールも常時注入
        f"- 言語: {cfg.language}\n"
        f"- 日時: {now.isoformat(timespec='seconds')}\n"
    )
    dynamics = ""
    if company: dynamics += f"- 会社: {company}\n"
    if profile: dynamics += f"- 分析プロファイル: {profile}\n"
    if sales_objective: dynamics += f"- 今回の営業目的: {sales_objective}\n"
    if audience: dynamics += f"- 想定読者: {audience}\n"

    # どの長文を入れるか
    chosen = sections
    if chosen is None:
        chosen = []
        if cfg.include_sales_doctrine: chosen.append("sales_doctrine")
        if cfg.include_research_framework: chosen.append("research_framework")
        if cfg.include_sources_toolkit: chosen.append("sources_toolkit")
        if cfg.include_activation_hints: chosen.append("activation_hints")

    long_blocks = [getattr(cfg, k) for k in chosen if getattr(cfg, k, None)]

    notes = ""
    if extra_notes:
        notes = "- 補足ルール:\n" + "".join([f"  - {n}\n" for n in extra_notes])

    return header + core + dynamics + ("\n".join(long_blocks) + ("\n" if long_blocks else "")) + notes

# ▶ フル分析用のユーティリティ（毎回これを呼ぶだけ）
def build_uc_for_company_analysis_full(
    company: str | None,
    *,
    sales_objective: str | None = None,
    audience: str | None = None,
    cfg: UniversalContextConfig | None = None
) -> str:
    cfg = cfg or UniversalContextConfig(
        include_sales_doctrine=True,
        include_research_framework=True,
        include_sources_toolkit=True,
        include_activation_hints=True,
    )
    return build_universal_context(
        cfg,
        company=company,
        sales_objective=sales_objective,
        audience=audience,
        profile="client_deepdive",
        sections=["sales_doctrine", "research_framework", "sources_toolkit", "activation_hints"],
    )
