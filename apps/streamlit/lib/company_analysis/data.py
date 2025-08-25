from __future__ import annotations
from dataclasses import dataclass
from typing import Optional


@dataclass
class SearchHit:
    title: str
    url: str
    snippet: str
    published: Optional[str] = None
