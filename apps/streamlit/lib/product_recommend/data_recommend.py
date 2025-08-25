from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Optional, Dict

@dataclass
class ProductItem:
    """商材CSVの1行を正規化したもの"""
    id: str
    name: str
    category: str | None
    price: Optional[float]
    description: str | None
    tags: str | None

    def to_dict(self) -> Dict:
        return asdict(self)

@dataclass
class ProductRecommendation:
    """推薦結果（UI/スライドに流用）"""
    id: str
    name: str
    category: str | None
    price: Optional[float]
    score: float  # 0.0〜1.0（信頼度/関連度）
    reason: str   # おすすめ理由（LLM生成 or 簡易理由）

    def to_dict(self) -> Dict:
        return asdict(self)
