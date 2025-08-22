"""
メッセージAPI
案件内の会話履歴管理
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import uuid4
from datetime import datetime

from ...db.session import get_db
from ...db.models import Item, Message
from ...schemas.messages import MessageCreate, MessageResponse

router = APIRouter(prefix="/items/{item_id}/messages", tags=["messages"])

@router.get("/", response_model=List[MessageResponse])
def get_messages(
    item_id: str,
    skip: int = 0,
    limit: int = 50,
    role: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    指定された案件のメッセージ履歴を取得
    """
    # 案件の存在確認
    item = db.query(Item).filter(Item.id == item_id).first()
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Item not found"
        )
    
    # メッセージクエリを構築
    query = db.query(Message).filter(Message.item_id == item_id)
    
    if role:
        query = query.filter(Message.role == role)
    
    messages = query.order_by(Message.created_at.asc()).offset(skip).limit(limit).all()
    
    return [
        MessageResponse(
            id=msg.id,
            item_id=msg.item_id,
            role=msg.role,
            content=msg.content,
            sources_json=msg.sources_json,
            created_at=msg.created_at
        )
        for msg in messages
    ]

@router.get("/{message_id}", response_model=MessageResponse)
def get_message(
    item_id: str,
    message_id: str,
    db: Session = Depends(get_db)
):
    """
    指定されたメッセージの詳細を取得
    """
    message = db.query(Message).filter(
        Message.id == message_id,
        Message.item_id == item_id
    ).first()
    
    if not message:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Message not found"
        )
    
    return MessageResponse(
        id=message.id,
        item_id=message.item_id,
        role=message.role,
        content=message.content,
        sources_json=message.sources_json,
        created_at=message.created_at
    )

@router.post("/", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
def create_message(
    item_id: str,
    message: MessageCreate,
    db: Session = Depends(get_db)
):
    """
    新しいメッセージを作成
    """
    # 案件の存在確認
    item = db.query(Item).filter(Item.id == item_id).first()
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Item not found"
        )
    
    # メッセージを作成
    db_message = Message(
        id=str(uuid4()),
        item_id=item_id,
        role=message.role,
        content=message.content,
        sources_json=message.sources_json,
        created_at=datetime.utcnow().isoformat()
    )
    
    db.add(db_message)
    db.commit()
    db.refresh(db_message)
    
    return MessageResponse(
        id=db_message.id,
        item_id=db_message.item_id,
        role=db_message.role,
        content=db_message.content,
        sources_json=db_message.sources_json,
        created_at=db_message.created_at
    )

@router.delete("/{message_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_message(
    item_id: str,
    message_id: str,
    db: Session = Depends(get_db)
):
    """
    メッセージを削除
    """
    message = db.query(Message).filter(
        Message.id == message_id,
        Message.item_id == item_id
    ).first()
    
    if not message:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Message not found"
        )
    
    db.delete(message)
    db.commit()
    
    return None

@router.get("/search/", response_model=List[MessageResponse])
def search_messages(
    item_id: str,
    query: str,
    limit: int = 10,
    db: Session = Depends(get_db)
):
    """
    案件内のメッセージを全文検索
    FTS5を使用して検索
    """
    # 案件の存在確認
    item = db.query(Item).filter(Item.id == item_id).first()
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Item not found"
        )
    
    # FTS5を使用した検索
    # 実際のクエリはSQLAlchemyのtext()を使用
    try:
        from sqlalchemy import text
        
        # FTS5検索クエリ
        fts_query = text("""
            SELECT m.id, m.item_id, m.role, m.content, m.sources_json, m.created_at,
                   rank
            FROM messages_fts fts
            JOIN messages m ON m.rowid = fts.rowid
            WHERE fts.content MATCH :query 
              AND fts.item_id = :item_id
            ORDER BY rank
            LIMIT :limit
        """)
        
        result = db.execute(fts_query, {
            "query": query,
            "item_id": item_id,
            "limit": limit
        }).fetchall()
        
        return [
            MessageResponse(
                id=row.id,
                item_id=row.item_id,
                role=row.role,
                content=row.content,
                sources_json=row.sources_json,
                created_at=row.created_at
            )
            for row in result
        ]
        
    except Exception as e:
        # FTS5が利用できない場合は通常のLIKE検索にフォールバック
        messages = db.query(Message).filter(
            Message.item_id == item_id,
            Message.content.contains(query)
        ).order_by(Message.created_at.desc()).limit(limit).all()
        
        return [
            MessageResponse(
                id=msg.id,
                item_id=msg.item_id,
                role=msg.role,
                content=msg.content,
                sources_json=msg.sources_json,
                created_at=msg.created_at
            )
            for msg in messages
        ]