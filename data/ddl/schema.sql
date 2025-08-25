-- 案件管理システム データベーススキーマ
-- SQLite + FTS5 を使用

-- 案件（カード）テーブル
CREATE TABLE IF NOT EXISTS items (
  id            TEXT PRIMARY KEY,          -- UUID
  title         TEXT NOT NULL,
  company_name  TEXT NOT NULL,
  description   TEXT,
  created_at    TEXT NOT NULL,             -- ISO8601形式
  updated_at    TEXT NOT NULL              -- ISO8601形式
);

-- 会話ログ（案件内）テーブル
CREATE TABLE IF NOT EXISTS messages (
  id           TEXT PRIMARY KEY,          -- UUID
  item_id      TEXT NOT NULL REFERENCES items(id) ON DELETE CASCADE,
  role         TEXT NOT NULL,             -- user | assistant | system
  content      TEXT NOT NULL,
  sources_json TEXT,                      -- 参照ID/URL等をJSONで格納
  created_at   TEXT NOT NULL              -- ISO8601形式
);

-- メッセージの全文検索テーブル（FTS5）
CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts USING fts5(
  content, 
  item_id UNINDEXED, 
  tokenize='unicode61'
);

-- FTS5 同期トリガー（INSERT）
CREATE TRIGGER IF NOT EXISTS messages_ai AFTER INSERT ON messages
BEGIN
  INSERT INTO messages_fts(rowid, content, item_id) 
  VALUES (new.rowid, new.content, new.item_id);
END;

-- FTS5 同期トリガー（DELETE）
CREATE TRIGGER IF NOT EXISTS messages_ad AFTER DELETE ON messages
BEGIN
  INSERT INTO messages_fts(messages_fts, rowid, content, item_id) 
  VALUES ('delete', old.rowid, old.content, old.item_id);
END;

-- FTS5 同期トリガー（UPDATE）
CREATE TRIGGER IF NOT EXISTS messages_au AFTER UPDATE ON messages
BEGIN
  INSERT INTO messages_fts(messages_fts, rowid, content, item_id) 
  VALUES ('delete', old.rowid, old.content, old.item_id);
  INSERT INTO messages_fts(rowid, content, item_id) 
  VALUES (new.rowid, new.content, new.item_id);
END;

-- 商材テーブル（DatasetA統合：可変列はJSON）
CREATE TABLE IF NOT EXISTS products (
  id          TEXT PRIMARY KEY,           -- 生成UUID or ハッシュ
  category    TEXT NOT NULL,              -- cpu, case-fan, keyboard等
  name        TEXT NOT NULL,
  price       REAL,
  specs_json  TEXT,                       -- 可変カラムをJSONで格納
  source_csv  TEXT NOT NULL               -- 元のCSVファイル名
);

-- 商材テーブルのインデックス
CREATE INDEX IF NOT EXISTS idx_products_cat_name ON products(category, name);
CREATE INDEX IF NOT EXISTS idx_products_category ON products(category);

-- 取引履歴テーブル（案件専用）
CREATE TABLE IF NOT EXISTS history (
  item_id          TEXT NOT NULL REFERENCES items(id) ON DELETE CASCADE,
  id               TEXT NOT NULL,          -- CSVのUUID（取引ID）
  order_date       TEXT,                   -- 発注日
  delivery_date    TEXT,                   -- 納期
  invoice_date     TEXT,                   -- 請求日
  business_partners TEXT NOT NULL,         -- 取引先企業名
  category         TEXT,                   -- 商品カテゴリ
  product_name     TEXT,                   -- 商品名
  quantity         REAL,                   -- 数量
  unit_price       REAL,                   -- 単価
  amount           REAL,                   -- 総額
  PRIMARY KEY(item_id, id)                 -- 案件ごとの一意制約
);

-- 取引履歴テーブルのインデックス
CREATE INDEX IF NOT EXISTS idx_hist_item_date ON history(item_id, order_date);
CREATE INDEX IF NOT EXISTS idx_hist_item_cat ON history(item_id, category);
CREATE INDEX IF NOT EXISTS idx_hist_item_partner ON history(item_id, business_partners);

-- 初期データ投入用のビュー（取引サマリ）
CREATE VIEW IF NOT EXISTS v_item_summary AS
SELECT 
  i.id as item_id,
  i.title,
  i.company_name,
  i.description,
  i.created_at,
  i.updated_at,
  COUNT(h.id) as transaction_count,
  COALESCE(SUM(h.amount), 0) as total_amount,
  MAX(h.order_date) as last_order_date,
  -- ユーザーが送信したチャット回数
  (SELECT COUNT(*) FROM messages WHERE item_id = i.id AND role = 'user') as user_message_count
FROM items i
LEFT JOIN history h ON i.id = h.item_id
GROUP BY i.id, i.title, i.company_name, i.description, i.created_at, i.updated_at;