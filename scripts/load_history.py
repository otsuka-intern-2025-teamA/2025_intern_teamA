#!/usr/bin/env python3
"""
取引履歴データをSQLiteにロードするスクリプト

使用方法:
  python scripts/load_history.py --item ITEM_ID --company "株式会社〇〇"
  python scripts/load_history.py --item ITEM_ID --company "株式会社〇〇" --csv data/csv/trade_history_dummy_100.csv
"""
import argparse
import sqlite3
import uuid
import hashlib
from pathlib import Path
import pandas as pd
import logging
import sys

# プロジェクトルートをPythonパスに追加
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# ログ設定
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def normalize_company_name(company_name: str) -> str:
    """
    企業名の表記ゆれを正規化
    取引履歴CSVと案件の企業名をマッチングするための関数
    """
    if not company_name:
        return ""
    
    # 基本的な正規化
    normalized = company_name.strip()
    
    # 株式会社の略記統一（例）
    # 実際の運用では、より詳細なマッピングテーブルを用意することを推奨
    replacements = {
        "㈱": "株式会社",
        "(株)": "株式会社",
        "（株）": "株式会社",
        "株式会社　": "株式会社",  # 全角スペース除去
    }
    
    for old, new in replacements.items():
        normalized = normalized.replace(old, new)
    
    return normalized

def load_history_for_item(csv_path: Path, item_id: str, target_company: str, conn: sqlite3.Connection) -> int:
    """
    指定された企業の取引履歴を案件にロード
    """
    logger.info(f"Loading history from {csv_path} for company '{target_company}' into item {item_id}")
    
    try:
        # CSVファイルを読み込み
        df = pd.read_csv(csv_path)
        logger.info(f"Loaded {len(df)} rows from CSV")
        
        # 必要なカラムの確認
        required_columns = ['business_partners']
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            logger.error(f"Missing required columns: {missing_columns}")
            return 0
        
        # 企業名の正規化
        target_company_normalized = normalize_company_name(target_company)
        
        # 該当企業の取引履歴を抽出
        df['business_partners_normalized'] = df['business_partners'].apply(normalize_company_name)
        filtered_df = df[df['business_partners_normalized'] == target_company_normalized]
        
        logger.info(f"Found {len(filtered_df)} transactions for company '{target_company_normalized}'")
        
        if len(filtered_df) == 0:
            # マッチングが完全一致しない場合、部分一致を試行
            logger.info("Trying partial matching...")
            filtered_df = df[df['business_partners_normalized'].str.contains(target_company_normalized, na=False)]
            logger.info(f"Partial match found {len(filtered_df)} transactions")
        
        if len(filtered_df) == 0:
            logger.warning(f"No transactions found for company '{target_company}'")
            # 利用可能な企業名をログ出力（デバッグ用）
            unique_companies = df['business_partners'].dropna().unique()[:10]  # 最初の10件
            logger.info(f"Available companies (sample): {list(unique_companies)}")
            return 0
        
        # データベースに挿入
        inserted_count = 0
        
        for _, row in filtered_df.iterrows():
            # UUIDが存在しない場合は生成
            if 'id' in row and pd.notna(row['id']):
                transaction_id = str(row['id'])
            else:
                # ユニークなIDを生成
                content = f"{item_id}:{row.get('order_date', '')}:{row.get('product_name', '')}:{row.get('amount', '')}"
                transaction_id = hashlib.md5(content.encode('utf-8')).hexdigest()
            
            try:
                # 取引履歴を挿入（UPSERT）
                conn.execute("""
                    INSERT OR REPLACE INTO history (
                        item_id, id, order_date, delivery_date, invoice_date,
                        business_partners, category, product_name, quantity, unit_price, amount
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    item_id,
                    transaction_id,
                    row.get('order_date'),
                    row.get('delivery_date'),
                    row.get('invoice_date'),
                    row.get('business_partners'),
                    row.get('category'),
                    row.get('product_name'),
                    row.get('quantity'),
                    row.get('unit_price'),
                    row.get('amount')
                ))
                inserted_count += 1
                
            except Exception as e:
                logger.error(f"Error inserting transaction {transaction_id}: {e}")
                continue
        
        logger.info(f"Successfully inserted {inserted_count} transactions")
        return inserted_count
        
    except Exception as e:
        logger.error(f"Error loading history: {e}")
        return 0

def main():
    parser = argparse.ArgumentParser(description='Load transaction history for a specific item')
    parser.add_argument('--item', required=True, help='Target item ID')
    parser.add_argument('--company', required=True, help='Company name to filter transactions')
    parser.add_argument('--csv', default='data/csv/trade_history_dummy_100.csv', help='CSV file path')
    parser.add_argument('--db-path', default='data/sqlite/app.db', help='Database path')
    
    args = parser.parse_args()
    
    # パス設定
    db_path = Path(args.db_path)
    csv_path = Path(args.csv)
    
    if not csv_path.exists():
        logger.error(f"CSV file not found: {csv_path}")
        return 1
    
    if not db_path.exists():
        logger.error(f"Database file not found: {db_path}")
        return 1
    
    try:
        # データベース接続
        conn = sqlite3.connect(str(db_path))
        
        # 案件の存在確認
        cursor = conn.cursor()
        cursor.execute("SELECT id, title, company_name FROM items WHERE id = ?", (args.item,))
        item_result = cursor.fetchone()
        
        if not item_result:
            logger.error(f"Item not found: {args.item}")
            # 利用可能な案件一覧を表示
            cursor.execute("SELECT id, title, company_name FROM items")
            items = cursor.fetchall()
            logger.info("Available items:")
            for item_id, title, company in items:
                logger.info(f"  {item_id[:8]}... | {title} | {company}")
            return 1
        
        item_id, item_title, item_company = item_result
        logger.info(f"Target item: {item_title} ({item_company})")
        
        # 既存の履歴数を確認
        cursor.execute("SELECT COUNT(*) FROM history WHERE item_id = ?", (args.item,))
        existing_count = cursor.fetchone()[0]
        
        if existing_count > 0:
            logger.info(f"Item already has {existing_count} history records")
            response = input("Replace existing history? (y/N): ")
            if response.lower() == 'y':
                cursor.execute("DELETE FROM history WHERE item_id = ?", (args.item,))
                logger.info("Existing history cleared")
        
        # 履歴データをロード
        inserted_count = load_history_for_item(csv_path, args.item, args.company, conn)
        
        if inserted_count > 0:
            conn.commit()
            logger.info(f"Transaction committed: {inserted_count} records")
            
            # 結果の要約を表示
            cursor.execute("""
                SELECT category, COUNT(*), SUM(amount), MAX(order_date)
                FROM history 
                WHERE item_id = ? AND category IS NOT NULL
                GROUP BY category
                ORDER BY SUM(amount) DESC
            """, (args.item,))
            
            categories = cursor.fetchall()
            if categories:
                logger.info("Loaded history summary by category:")
                for category, count, total_amount, last_date in categories:
                    logger.info(f"  {category}: {count}件, ¥{total_amount:,.0f}, 最終: {last_date}")
        else:
            logger.warning("No data was loaded")
            
    except Exception as e:
        logger.error(f"Loading failed: {e}")
        if 'conn' in locals():
            conn.rollback()
        return 1
    finally:
        if 'conn' in locals():
            conn.close()
    
    return 0

if __name__ == '__main__':
    exit(main())