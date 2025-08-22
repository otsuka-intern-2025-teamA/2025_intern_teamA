
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict

@dataclass
class SearchHit:
    title: str
    url: str
    snippet: str
    published: Optional[str] = None

@dataclass
class CompanyReport:
    company: str
    overview: str
    offerings: str
    customers_and_markets: str
    recent_news: str
    competitors: str
    risks: str
    suggested_questions: List[str] = field(default_factory=list)
    sources: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return asdict(self)
