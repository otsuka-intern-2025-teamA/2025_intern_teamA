#!/usr/bin/env python3
"""
取引履歴データを案件ごとにSQLiteにロードするスクリプト

使用方法:
  python scripts/load_history.py --item ITEM_ID --company "株式会社ABC"
  python scripts/load_history.py --item ITEM_ID --company "株式会社ABC" --csv-file data/csv/products/trade_history_dummy_100.csv
"""
import argparse
import sqlite3
import logging
from pathlib import Path
import pandas as pd
import re

# ログ設定
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def normalize_company_name(company_name: str) -> str:
    """企業名を正規化（表記ゆれ対応）"""
    if not company_name:
        return ""
    
    # 基本的な正規化ルール
    normalized = company_name.strip()
    
    # 全角・半角の統一
    normalized = normalized.replace('（', '(').replace('）', ')')
    normalized = normalized.replace('　', ' ')  # 全角スペースを半角に
    
    # 株式会社の表記統一
    normalized = re.sub(r'株式会社|㈱|\(株\)', '株式会社', normalized)
    
    # 有限会社の表記統一
    normalized = re.sub(r'有限会社|㈲|\(有\)', '有限会社', normalized)
    
    # 合同会社の表記統一
    normalized = re.sub(r'合同会社|合資会社|合名会社', '合同会社', normalized)
    
    # Co.,Ltd. などの表記
    normalized = re.sub(r'Co\.,?\s*Ltd\.?|株式会社|Corporation|Corp\.?', '株式会社', normalized, flags=re.IGNORECASE)
    
    return normalized.strip()

def load_history_for_item(item_id: str, company_name: str, csv_path: Path, conn: sqlite3.Connection):
    """指定した企業の取引履歴を案件にロード"""
    logger.info(f"Loading history for item {item_id}, company: {company_name}")
    
    try:
        df = pd.read_csv(csv_path)
        logger.info(f"Loaded {len(df)} total transactions from {csv_path}")
        
        # 企業名を正規化
        normalized_target = normalize_company_name(company_name)
        logger.info(f"Normalized target company: {normalized_target}")
        
        # 企業名でフィルタリング
        if 'business_partners' not in df.columns:
            logger.error("Column 'business_partners' not found in CSV")
            return 0
        
        # 正規化して比較
        df['normalized_partners'] = df['business_partners'].apply(normalize_company_name)
        filtered_df = df[df['normalized_partners'] == normalized_target]
        
        logger.info(f"Found {len(filtered_df)} transactions for {normalized_target}")
        
        if len(filtered_df) == 0:
            # 利用可能な企業名を表示
            unique_companies = df['normalized_partners'].unique()[:10]  # 最初の10社
            logger.info(f"Available companies (first 10): {list(unique_companies)}")
            return 0
        
        inserted_count = 0
        updated_count = 0
        
        for _, row in filtered_df.iterrows():
            # 必要なカラムを抽出
            transaction_data = {
                'item_id': item_id,
                'id': row.get('id', ''),  # 取引ID
                'order_date': row.get('order_date', None),
                'delivery_date': row.get('delivery_date', None),
                'invoice_date': row.get('invoice_date', None),
                'business_partners': row.get('business_partners', ''),
                'category': row.get('category', None),
                'product_name': row.get('product_name', None),
                'quantity': pd.to_numeric(row.get('quantity', 0), errors='coerce'),
                'unit_price': pd.to_numeric(row.get('unit_price', 0), errors='coerce'),
                'amount': pd.to_numeric(row.get('amount', 0), errors='coerce')
            }
            
            # NaN値を None に変換
            for key, value in transaction_data.items():
                if pd.isna(value):
                    transaction_data[key] = None
            
            try:
                # UPSERT処理（INSERT OR REPLACE）
                cursor = conn.execute("""
                    SELECT COUNT(*) FROM history WHERE item_id = ? AND id = ?
                """, (item_id, transaction_data['id']))
                
                exists = cursor.fetchone()[0] > 0
                
                conn.execute("""
                    INSERT OR REPLACE INTO history 
                    (item_id, id, order_date, delivery_date, invoice_date, business_partners, 
                     category, product_name, quantity, unit_price, amount)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    transaction_data['item_id'], transaction_data['id'],
                    transaction_data['order_date'], transaction_data['delivery_date'],
                    transaction_data['invoice_date'], transaction_data['business_partners'],
                    transaction_data['category'], transaction_data['product_name'],
                    transaction_data['quantity'], transaction_data['unit_price'],
                    transaction_data['amount']
                ))
                
                if exists:
                    updated_count += 1
                else:
                    inserted_count += 1
                    
            except Exception as e:
                logger.error(f"Error inserting transaction {transaction_data.get('id', 'unknown')}: {e}")
                continue
        
        logger.info(f"Processed {inserted_count} new transactions, {updated_count} updated for item {item_id}")
        return inserted_count + updated_count
        
    except Exception as e:
        logger.error(f"Error loading history: {e}")
        return 0

def main():
    parser = argparse.ArgumentParser(description='Load transaction history for a specific item/company')
    parser.add_argument('--item', required=True, help='Item ID (UUID)')
    parser.add_argument('--company', required=True, help='Company name to filter transactions')
    parser.add_argument('--csv-file', default='data/csv/products/trade_history_dummy_100.csv', help='Transaction CSV file path')
    parser.add_argument('--db-path', default='data/sqlite/app.db', help='Database path')
    
    args = parser.parse_args()
    
    # ファイルパスの設定
    db_path = Path(args.db_path)
    csv_path = Path(args.csv_file)
    
    # ファイル存在チェック
    if not csv_path.exists():
        logger.error(f"CSV file not found: {csv_path}")
        return 1
    
    # データベースディレクトリを作成
    db_path.parent.mkdir(parents=True, exist_ok=True)
    
    # データベース接続
    conn = sqlite3.connect(str(db_path))
    
    try:
        # スキーマを初期化（存在しない場合）
        schema_path = Path('data/ddl/schema.sql')
        if schema_path.exists():
            with open(schema_path, 'r', encoding='utf-8') as f:
                conn.executescript(f.read())
        
        # 指定された案件が存在するかチェック
        cursor = conn.execute("SELECT id, company_name FROM items WHERE id = ?", (args.item,))
        item_row = cursor.fetchone()
        
        if not item_row:
            logger.error(f"Item with ID {args.item} not found in database")
            logger.info("Available items:")
            cursor = conn.execute("SELECT id, title, company_name FROM items LIMIT 10")
            for row in cursor.fetchall():
                logger.info(f"  {row[0]}: {row[1]} ({row[2]})")
            return 1
        
        logger.info(f"Loading history for item: {item_row[0]} - {item_row[1]}")
        
        # 取引履歴をロード
        count = load_history_for_item(args.item, args.company, csv_path, conn)
        
        if count > 0:
            # コミット
            conn.commit()
            logger.info(f"Successfully loaded {count} transactions")
            
            # 統計情報を表示
            cursor = conn.execute("""
                SELECT 
                    COUNT(*) as transaction_count,
                    SUM(amount) as total_amount,
                    MIN(order_date) as first_order,
                    MAX(order_date) as last_order
                FROM history 
                WHERE item_id = ?
            """, (args.item,))
            
            stats = cursor.fetchone()
            if stats:
                logger.info(f"Item statistics: {stats[0]} transactions, total amount: {stats[1]}")
                logger.info(f"Period: {stats[2]} to {stats[3]}")
        else:
            logger.warning("No transactions were loaded")
        
    except Exception as e:
        logger.error(f"Error during loading: {e}")
        conn.rollback()
        return 1
    finally:
        conn.close()
    
    return 0

if __name__ == '__main__':
    exit(main())
