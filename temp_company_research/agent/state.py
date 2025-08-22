from dataclasses import dataclass, field
from typing import List, Dict, Set, Optional

@dataclass
class Doc:
    url: str
    title: str
    text: str

@dataclass
class AgentState:
    company: str
    locale: str
    sections: List[str]

    # память/рабочее состояние
    known_urls: Set[str] = field(default_factory=set)
    docs: List[Doc] = field(default_factory=list)
    pending_queries: List[str] = field(default_factory=list)

    # контроль итераций
    step: int = 0
    max_steps: int = 5

    # выход
    briefings: Dict[str, str] = field(default_factory=dict)
    sources: List[Dict] = field(default_factory=list)

    def coverage_hint(self) -> Dict[str, int]:
        """Грубая метрика покрытия по ключевым словам по секциям."""
        txt = " ".join(d.text[:5000] for d in self.docs).lower()
        def count_any(words: List[str]) -> int:
            return sum(txt.count(w) for w in words)
        return {
            "products": count_any(["product", "service", "製品", "サービス"]),
            "market": count_any(["competitor", "競合", "market share", "シェア"]),
            "financials": count_any(["revenue", "売上", "決算", "収益", "funding"]),
            "news": count_any(["2024", "2025", "news", "発表", "プレス"]),
            "risks": count_any(["risk", "リスク", "規制", "訴訟", "罰金", "コンプライアンス"]),
            "profile": count_any(["overview", "会社概要", "沿革", "history", "business model"]),
        }

    def missing_sections(self) -> List[str]:
        cov = self.coverage_hint()
        wanted = set(self.sections)
        # "достаточность" очень грубая: нет ни одного ключевого слова → считаем не покрыто
        missing = [s for s in wanted if cov.get(s, 0) == 0]
        return missing
