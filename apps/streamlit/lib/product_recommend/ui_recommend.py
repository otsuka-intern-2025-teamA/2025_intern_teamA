from __future__ import annotations
import streamlit as st
import pandas as pd
from typing import List
from .data_recommend import ProductRecommendation

def render_recommendations_table(recs: List[ProductRecommendation], *, height: int = 480):
    """推薦結果を表形式で表示（スライド作成モジュールからも使い回し可）"""
    if not recs:
        st.info("候補がありません。条件を変えて再取得してください。")
        return

    df = pd.DataFrame([r.to_dict() for r in recs])
    # 表示用の列順・フォーマット
    show = df[["name", "category", "price", "score", "reason", "id"]].rename(columns={
        "name": "商品名",
        "category": "カテゴリ",
        "price": "価格",
        "score": "スコア",
        "reason": "理由",
        "id": "_id",
    })
    st.dataframe(
        show,
        height=height,
        use_container_width=True,
    )
