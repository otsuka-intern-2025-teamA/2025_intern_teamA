"""
SQLAlchemyモデル定義
案件管理システム用のデータベースモデル
"""

import uuid
from datetime import datetime

from sqlalchemy import Column, Float, ForeignKey, Index, String, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()


class Item(Base):
    """案件(カード)モデル"""

    __tablename__ = "items"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    title = Column(String, nullable=False)
    company_name = Column(String, nullable=False)
    description = Column(Text)
    created_at = Column(String, nullable=False, default=lambda: datetime.utcnow().isoformat())
    updated_at = Column(String, nullable=False, default=lambda: datetime.utcnow().isoformat())

    # リレーションシップ
    messages = relationship("Message", back_populates="item", cascade="all, delete-orphan")
    history = relationship("History", back_populates="item", cascade="all, delete-orphan")


class Message(Base):
    """会話ログモデル"""

    __tablename__ = "messages"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    item_id = Column(String, ForeignKey("items.id", ondelete="CASCADE"), nullable=False)
    role = Column(String, nullable=False)  # user | assistant | system
    content = Column(Text, nullable=False)
    sources_json = Column(Text)  # 参照ID/URL等をJSONで格納
    created_at = Column(String, nullable=False, default=lambda: datetime.utcnow().isoformat())

    # リレーションシップ
    item = relationship("Item", back_populates="messages")


class Product(Base):
    """商材モデル(DatasetA統合)"""

    __tablename__ = "products"

    id = Column(String, primary_key=True)  # 生成UUID or ハッシュ
    category = Column(String, nullable=False)  # cpu, case-fan, keyboard等
    name = Column(String, nullable=False)
    price = Column(Float)
    specs_json = Column(Text)  # 可変カラムをJSONで格納
    source_csv = Column(String, nullable=False)  # 元のCSVファイル名


# 商材テーブルのインデックス
Index("idx_products_cat_name", Product.category, Product.name)
Index("idx_products_category", Product.category)


class History(Base):
    """取引履歴モデル(案件専用)"""

    __tablename__ = "history"

    item_id = Column(String, ForeignKey("items.id", ondelete="CASCADE"), primary_key=True)
    id = Column(String, primary_key=True)  # CSVのUUID(取引ID)
    order_date = Column(String)  # 発注日
    delivery_date = Column(String)  # 納期
    invoice_date = Column(String)  # 請求日
    business_partners = Column(String, nullable=False)  # 取引先企業名
    category = Column(String)  # 商品カテゴリ
    product_name = Column(String)  # 商品名
    quantity = Column(Float)  # 数量
    unit_price = Column(Float)  # 単価
    amount = Column(Float)  # 総額

    # リレーションシップ
    item = relationship("Item", back_populates="history")


# 取引履歴テーブルのインデックス
Index("idx_hist_item_date", History.item_id, History.order_date)
Index("idx_hist_item_cat", History.item_id, History.category)
Index("idx_hist_item_partner", History.item_id, History.business_partners)
