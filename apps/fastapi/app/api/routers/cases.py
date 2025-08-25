"""
案件CRUD API
案件（カード）の作成、取得、更新、削除を管理
シンプルなdict形式でデータをやり取り
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional, Dict, Any
from uuid import uuid4
from datetime import datetime

from ...db.session import get_db
from ...db.models import Item, History, Message

router = APIRouter(prefix="/items", tags=["cases"])

@router.get("/")
def get_items(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
) -> List[Dict[str, Any]]:
    """
    全案件の一覧を取得（サマリ情報付き）
    カード表示用のデータを返す
    """
    items = db.query(Item).offset(skip).limit(limit).all()
    
    result = []
    for item in items:
        # 取引履歴の統計を取得
        history_stats = db.query(
            func.count(History.id).label('transaction_count'),
            func.coalesce(func.sum(History.amount), 0).label('total_amount'),
            func.max(History.order_date).label('last_order_date')
        ).filter(History.item_id == item.id).first()
        
        # ユーザーが送信したチャット回数を取得
        user_message_count = db.query(func.count(Message.id)).filter(
            Message.item_id == item.id,
            Message.role == 'user'
        ).scalar() or 0
        
        # シンプルな辞書形式で返す
        item_data = {
            "id": item.id,
            "title": item.title,
            "company_name": item.company_name,
            "description": item.description,
            "created_at": item.created_at,
            "updated_at": item.updated_at,
            "transaction_count": history_stats.transaction_count or 0,
            "total_amount": float(history_stats.total_amount or 0.0),
            "last_order_date": history_stats.last_order_date,
            "user_message_count": user_message_count
        }
        result.append(item_data)
    
    return result

@router.get("/{item_id}")
def get_item(item_id: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """指定された案件の詳細情報を取得"""
    item = db.query(Item).filter(Item.id == item_id).first()
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Item not found"
        )
    
    return {
        "id": item.id,
        "title": item.title,
        "company_name": item.company_name,
        "description": item.description,
        "created_at": item.created_at,
        "updated_at": item.updated_at
    }

@router.post("/", status_code=status.HTTP_201_CREATED)
def create_item(data: Dict[str, Any], db: Session = Depends(get_db)) -> Dict[str, Any]:
    """新しい案件を作成"""
    now = datetime.utcnow().isoformat()
    
    db_item = Item(
        id=str(uuid4()),
        title=data.get("title", ""),
        company_name=data.get("company_name", ""),
        description=data.get("description"),
        created_at=now,
        updated_at=now
    )
    
    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    
    return {
        "id": db_item.id,
        "title": db_item.title,
        "company_name": db_item.company_name,
        "description": db_item.description,
        "created_at": db_item.created_at,
        "updated_at": db_item.updated_at
    }

@router.put("/{item_id}")
def update_item(item_id: str, data: Dict[str, Any], db: Session = Depends(get_db)) -> Dict[str, Any]:
    """案件情報を更新"""
    db_item = db.query(Item).filter(Item.id == item_id).first()
    if not db_item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Item not found"
        )
    
    # 更新可能なフィールドを設定
    if "title" in data:
        db_item.title = data["title"]
    if "company_name" in data:
        db_item.company_name = data["company_name"]
    if "description" in data:
        db_item.description = data["description"]
    
    db_item.updated_at = datetime.utcnow().isoformat()
    
    db.commit()
    db.refresh(db_item)
    
    return {
        "id": db_item.id,
        "title": db_item.title,
        "company_name": db_item.company_name,
        "description": db_item.description,
        "created_at": db_item.created_at,
        "updated_at": db_item.updated_at
    }

@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_item(item_id: str, db: Session = Depends(get_db)):
    """案件を削除（関連データも全て削除）"""
    db_item = db.query(Item).filter(Item.id == item_id).first()
    if not db_item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Item not found"
        )
    
    db.delete(db_item)
    db.commit()
    
    return None