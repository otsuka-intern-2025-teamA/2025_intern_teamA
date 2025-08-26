"""
RAG検索・企業分析API
企業分析用のRAG処理とデータ取得機能
シンプルなdict形式でデータをやり取り
"""

import json
import logging
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from fastapi import APIRouter, Depends, HTTPException, status

from ...db.models import History, Item, Message, Product
from ...db.session import get_db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/analysis", tags=["analysis"])


@router.post("/query")
def analyze_company(data: dict[str, Any], db: Session = Depends(get_db)) -> dict[str, Any]:
    """
    企業分析を実行
    指定された案件のコンテキストを使用してRAG処理を行う

    入力データ形式:
    {
        "item_id": "案件ID",
        "question": "質問内容",
        "company_name": "企業名(オプション)",
        "top_k": 5
    }
    """
    # 必須パラメータのチェック
    item_id = data.get("item_id")
    question = data.get("question")
    if not item_id or not question:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="item_id and question are required")

    # 案件の存在確認
    item = db.query(Item).filter(Item.id == item_id).first()
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")

    # 企業名の設定(リクエストで指定されていない場合は案件の企業名を使用)
    target_company = data.get("company_name") or item.company_name
    top_k = data.get("top_k", 5)

    try:
        # コンテキスト情報を収集
        context_data = _gather_context(db, item_id, target_company, question, top_k)

        # ここで実際のLLM処理を行う(現在はモック)
        # TODO: 実際のRAG処理を実装
        analysis_result = _mock_analysis(target_company, question, context_data)

        # 結果をメッセージテーブルに保存
        sources_json = json.dumps(
            {
                "message_ids": context_data.get("message_ids", []),
                "history_ids": context_data.get("history_ids", []),
                "product_ids": context_data.get("product_ids", []),
            },
            ensure_ascii=False,
        )

        # ユーザーの質問を保存
        user_message = Message(item_id=item_id, role="user", content=question, sources_json=None)
        db.add(user_message)

        # アシスタントの回答を保存
        assistant_message = Message(
            item_id=item_id, role="assistant", content=analysis_result, sources_json=sources_json
        )
        db.add(assistant_message)

        db.commit()

        return {
            "result": analysis_result,
            "context_summary": context_data.get("summary", ""),
            "sources_used": context_data.get("sources_used", []),
        }

    except Exception as e:
        logger.error(f"Analysis error: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Analysis processing failed")


@router.post("/history/load")
def load_history(data: dict[str, Any], db: Session = Depends(get_db)) -> dict[str, Any]:
    """
    取引履歴を案件にロード
    外部スクリプトを呼び出してCSVデータを取り込む

    入力データ形式:
    {
        "item_id": "案件ID",
        "company_name": "企業名"
    }
    """
    # 必須パラメータのチェック
    item_id = data.get("item_id")
    company_name = data.get("company_name")
    if not item_id or not company_name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="item_id and company_name are required")

    # 案件の存在確認
    item = db.query(Item).filter(Item.id == item_id).first()
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")

    try:
        # 実際のロード処理はスクリプトで実行
        # ここではAPIレスポンスのみ返す
        # TODO: scripts/load_history.py を subprocess で呼び出し

        # 現在のロード状況を確認
        history_count = db.query(func.count(History.id)).filter(History.item_id == item_id).scalar()

        return {
            "message": f"History load initiated for company: {company_name}",
            "item_id": item_id,
            "current_history_count": history_count,
        }

    except Exception as e:
        logger.error(f"History load error: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="History loading failed")


def _gather_context(db: Session, item_id: str, company_name: str, question: str, top_k: int = 5) -> dict[str, Any]:
    """
    企業分析用のコンテキスト情報を収集
    """
    context = {"message_ids": [], "history_ids": [], "product_ids": [], "sources_used": [], "summary": ""}

    try:
        # 1. 過去の会話履歴から関連メッセージを検索(FTS5使用)
        # 実際の実装では、questionに基づいたFTS検索を行う
        messages = (
            db.query(Message).filter(Message.item_id == item_id).order_by(Message.created_at.desc()).limit(top_k).all()
        )

        context["message_ids"] = [msg.id for msg in messages]
        if messages:
            context["sources_used"].append(f"過去の会話履歴 {len(messages)}件")

        # 2. 取引履歴の要約情報を取得
        history_summary = (
            db.query(
                func.count(History.id).label("count"),
                func.sum(History.amount).label("total"),
                func.max(History.order_date).label("last_date"),
                History.category,
            )
            .filter(History.item_id == item_id)
            .group_by(History.category)
            .all()
        )

        if history_summary:
            total_transactions = sum([h.count for h in history_summary])
            total_amount = sum([h.total or 0 for h in history_summary])
            categories = [h.category for h in history_summary if h.category]

            context["summary"] += f"取引履歴: {total_transactions}件、総額: ¥{total_amount:,.0f}、"
            context["summary"] += f"主要カテゴリ: {', '.join(categories[:3])}"
            context["sources_used"].append(f"取引履歴 {total_transactions}件")

        # 3. 関連商材情報を検索
        if history_summary:
            categories = [h.category for h in history_summary if h.category]
            if categories:
                products = db.query(Product).filter(Product.category.in_(categories)).limit(top_k).all()

                context["product_ids"] = [p.id for p in products]
                if products:
                    context["sources_used"].append(f"関連商材 {len(products)}件")

    except Exception as e:
        logger.error(f"Context gathering error: {e}")
        context["summary"] = "コンテキスト情報の取得中にエラーが発生しました"

    return context


def _mock_analysis(company_name: str, question: str, context: dict[str, Any]) -> str:
    """
    企業分析のモック処理
    実際の実装では、LLMを使用して分析を行う
    """
    return f"""
{company_name}に関する分析結果:

質問: {question}

【分析概要】
{context.get("summary", "データが不足しています")}

【参照データ】
{", ".join(context.get("sources_used", ["データなし"]))}

※ この分析結果はサンプルです。実際の実装では、収集したコンテキストを基にLLMが詳細な分析を行います。
"""
