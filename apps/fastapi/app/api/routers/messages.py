"""
メッセージ管理API
案件内の会話ログの管理とFTS検索機能
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List, Dict, Any, Optional
from uuid import uuid4
from datetime import datetime

from ...db.session import get_db
from ...db.models import Message, Item

router = APIRouter(prefix="/items/{item_id}/messages", tags=["messages"])

@router.get("/")
def get_messages(
    item_id: str,
    skip: int = 0,
    limit: int = 50,
    search: Optional[str] = Query(None, description="FTS検索クエリ"),
    db: Session = Depends(get_db)
) -> List[Dict[str, Any]]:
    """
    指定案件のメッセージ一覧を取得
    searchパラメータが指定された場合はFTS検索を実行
    """
    # 案件の存在確認
    item = db.query(Item).filter(Item.id == item_id).first()
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Item not found"
        )
    
    if search:
        # FTS5を使用した全文検索
        try:
            # FTS検索クエリ
            query = text("""
                SELECT m.id, m.item_id, m.role, m.content, m.sources_json, m.created_at
                FROM messages m
                JOIN messages_fts fts ON m.rowid = fts.rowid
                WHERE fts.item_id = :item_id 
                AND fts MATCH :search_query
                ORDER BY rank
                LIMIT :limit OFFSET :skip
            """)
            
            results = db.execute(query, {
                "item_id": item_id,
                "search_query": search,
                "limit": limit,
                "skip": skip
            }).fetchall()
            
            messages = []
            for row in results:
                messages.append({
                    "id": row.id,
                    "item_id": row.item_id,
                    "role": row.role,
                    "content": row.content,
                    "sources_json": row.sources_json,
                    "created_at": row.created_at
                })
            
        except Exception as e:
            # FTS検索に失敗した場合は通常検索にフォールバック
            messages_query = db.query(Message).filter(
                Message.item_id == item_id,
                Message.content.contains(search)
            ).order_by(Message.created_at.desc()).offset(skip).limit(limit)
            
            messages = []
            for msg in messages_query.all():
                messages.append({
                    "id": msg.id,
                    "item_id": msg.item_id,
                    "role": msg.role,
                    "content": msg.content,
                    "sources_json": msg.sources_json,
                    "created_at": msg.created_at
                })
    else:
        # 通常の時系列順取得
        messages_query = db.query(Message).filter(
            Message.item_id == item_id
        ).order_by(Message.created_at.desc()).offset(skip).limit(limit)
        
        messages = []
        for msg in messages_query.all():
            messages.append({
                "id": msg.id,
                "item_id": msg.item_id,
                "role": msg.role,
                "content": msg.content,
                "sources_json": msg.sources_json,
                "created_at": msg.created_at
            })
    
    return messages

@router.post("/", status_code=status.HTTP_201_CREATED)
def create_message(
    item_id: str,
    data: Dict[str, Any],
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """新しいメッセージを作成"""
    # 案件の存在確認
    item = db.query(Item).filter(Item.id == item_id).first()
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Item not found"
        )
    
    # 必須フィールドのチェック
    if not data.get("role") or not data.get("content"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="role and content are required"
        )
    
    # メッセージ作成
    db_message = Message(
        id=str(uuid4()),
        item_id=item_id,
        role=data["role"],
        content=data["content"],
        sources_json=data.get("sources_json"),
        created_at=datetime.utcnow().isoformat()
    )
    
    db.add(db_message)
    db.commit()
    db.refresh(db_message)
    
    return {
        "id": db_message.id,
        "item_id": db_message.item_id,
        "role": db_message.role,
        "content": db_message.content,
        "sources_json": db_message.sources_json,
        "created_at": db_message.created_at
    }

@router.get("/{message_id}")
def get_message(
    item_id: str,
    message_id: str,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """指定されたメッセージの詳細を取得"""
    message = db.query(Message).filter(
        Message.id == message_id,
        Message.item_id == item_id
    ).first()
    
    if not message:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Message not found"
        )
    
    return {
        "id": message.id,
        "item_id": message.item_id,
        "role": message.role,
        "content": message.content,
        "sources_json": message.sources_json,
        "created_at": message.created_at
    }