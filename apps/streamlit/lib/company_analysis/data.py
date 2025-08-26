from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SearchHit:
    title: str
    url: str
    snippet: str
    published: str | None = None
