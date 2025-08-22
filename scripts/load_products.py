#!/usr/bin/env python3
"""
商材データ（DatasetA）をSQLiteにロードするスクリプト

使用方法:
  python scripts/load_products.py --replace
  python scripts/load_products.py --update
"""
import argparse
import json
import sqlite3
import uuid
import hashlib
from pathlib import Path
import pandas as pd
import logging

# ログ設定
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def generate_product_id(category: str, name: str, price: float = None) -> str:
    """商品の一意IDを生成（カテゴリ+商品名+価格のハッシュ）"""
    content = f"{category}:{name}:{price or ''}"
    return hashlib.md5(content.encode('utf-8')).hexdigest()

def normalize_price(price_str):
    """価格文字列を数値に変換（$マークや,を除去）"""
    if pd.isna(price_str):
        return None
    if isinstance(price_str, (int, float)):
        return float(price_str)
    
    # 文字列の場合、$マークやカンマを除去して数値化
    price_clean = str(price_str).replace('$', '').replace(',', '').strip()
    try:
        return float(price_clean)
    except (ValueError, TypeError):
        return None

def load_csv_to_products(csv_path: Path, category: str, conn: sqlite3.Connection):
    """単一のCSVファイルを商材テーブルにロード"""
    logger.info(f"Loading {csv_path} as category '{category}'")
    
    try:
        df = pd.read_csv(csv_path)
        logger.info(f"Loaded {len(df)} rows from {csv_path}")
        
        # 必須カラムをチェック
        if 'name' not in df.columns:
            logger.warning(f"'name' column not found in {csv_path}, skipping")
            return 0
        
        inserted_count = 0
        
        for _, row in df.iterrows():
            # 基本情報を抽出
            name = row.get('name', '')
            if not name or pd.isna(name):
                continue
                
            price = normalize_price(row.get('price'))
            
            # specs_json用のデータ（name, price以外のカラム）
            specs = {}
            for col in df.columns:
                if col not in ['name', 'price'] and not pd.isna(row[col]):
                    specs[col] = row[col]
            
            # 商品IDを生成
            product_id = generate_product_id(category, name, price)
            
            # データベースに挿入
            try:
                conn.execute("""
                    INSERT OR REPLACE INTO products (id, category, name, price, specs_json, source_csv)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (product_id, category, name, price, json.dumps(specs, ensure_ascii=False), csv_path.name))
                inserted_count += 1
            except Exception as e:
                logger.error(f"Error inserting product {name}: {e}")
                continue
        
        logger.info(f"Inserted {inserted_count} products from {category}")
        return inserted_count
        
    except Exception as e:
        logger.error(f"Error loading {csv_path}: {e}")
        return 0

def main():
    parser = argparse.ArgumentParser(description='Load product data from CSV files')
    parser.add_argument('--replace', action='store_true', help='Replace all existing product data')
    parser.add_argument('--update', action='store_true', help='Update existing product data')
    parser.add_argument('--db-path', default='data/sqlite/app.db', help='Database path')
    parser.add_argument('--csv-dir', default='data/csv/products', help='CSV directory path')
    
    args = parser.parse_args()
    
    if not args.replace and not args.update:
        logger.error("Specify either --replace or --update")
        return 1
    
    # データベースパスとCSVディレクトリのパス設定
    db_path = Path(args.db_path)
    csv_dir = Path(args.csv_dir)
    
    # データベースディレクトリを作成
    db_path.parent.mkdir(parents=True, exist_ok=True)
    
    if not csv_dir.exists():
        logger.error(f"CSV directory not found: {csv_dir}")
        return 1
    
    # データベース接続
    conn = sqlite3.connect(str(db_path))
    
    try:
        # スキーマを初期化（存在しない場合）
        schema_path = Path('data/ddl/schema.sql')
        if schema_path.exists():
            with open(schema_path, 'r', encoding='utf-8') as f:
                conn.executescript(f.read())
        
        # 既存データを削除（--replace の場合）
        if args.replace:
            logger.info("Removing existing product data...")
            conn.execute("DELETE FROM products")
        
        total_inserted = 0
        
        # DatasetA と DatasetB の両方をチェック
        for dataset_dir in ['DatasetA', 'DatasetB']:
            dataset_path = csv_dir / dataset_dir
            if not dataset_path.exists():
                logger.warning(f"Dataset directory not found: {dataset_path}")
                continue
                
            # CSVファイルを処理
            for csv_file in dataset_path.glob('*.csv'):
                # ファイル名からカテゴリを推定（拡張子を除去）
                category = csv_file.stem
                
                # 特別な処理が必要なファイル
                if category == 'laptop_dataset_cleaned_full':
                    category = 'laptop'
                
                count = load_csv_to_products(csv_file, category, conn)
                total_inserted += count
        
        # コミット
        conn.commit()
        logger.info(f"Successfully loaded {total_inserted} products total")
        
        # 統計情報を表示
        cursor = conn.execute("SELECT category, COUNT(*) FROM products GROUP BY category ORDER BY category")
        logger.info("Product count by category:")
        for category, count in cursor.fetchall():
            logger.info(f"  {category}: {count}")
        
    except Exception as e:
        logger.error(f"Error during loading: {e}")
        conn.rollback()
        return 1
    finally:
        conn.close()
    
    return 0

if __name__ == '__main__':
    exit(main())
