-- =========================================
-- 案件管理システム データベーススキーマ（安全版）
-- SQLite + FTS5（external content）を使用
-- =========================================

-- 重要：この接続で外部キーを有効化（永続ではないためアプリ側でも必須）
PRAGMA foreign_keys = ON;

-- ----------------------------
-- 親：案件（カード）
-- ----------------------------
CREATE TABLE IF NOT EXISTS items (
  id            TEXT PRIMARY KEY,          -- UUID
  title         TEXT NOT NULL,
  company_name  TEXT NOT NULL,
  description   TEXT,
  created_at    TEXT NOT NULL,             -- ISO8601
  updated_at    TEXT NOT NULL              -- ISO8601
);

-- ----------------------------
-- 子：会話ログ（案件内）
-- ----------------------------
CREATE TABLE IF NOT EXISTS messages (
  id           TEXT PRIMARY KEY,           -- UUID
  item_id      TEXT NOT NULL REFERENCES items(id) ON DELETE CASCADE,
  role         TEXT NOT NULL,              -- user | assistant | system
  content      TEXT NOT NULL,
  sources_json TEXT,                       -- 参照ID/URL等をJSONで格納
  created_at   TEXT NOT NULL               -- ISO8601
);

-- よく使うクエリ向けのインデックス（任意だが推奨）
CREATE INDEX IF NOT EXISTS idx_messages_item_created ON messages(item_id, created_at);

-- ================================================================
-- FTS5: messages の全文検索（external content 方式で堅牢に）
-- 既存のFTS/トリガーは互換のため一度DROPしてから再作成する
-- ================================================================
DROP TRIGGER IF EXISTS messages_ai;
DROP TRIGGER IF EXISTS messages_ad;
DROP TRIGGER IF EXISTS messages_au;
DROP TABLE   IF EXISTS messages_fts;

-- external content: 真の内容は messages に置き、
-- FTSは rowid でリンク。列ズレに強く、DELETEはrowidのみで同期可能。
CREATE VIRTUAL TABLE messages_fts USING fts5(
  content,                      -- 検索対象本文
  item_id UNINDEXED,            -- 絞り込み用（索引不要）
  content='messages',           -- 外部ソース：messages
  content_rowid='rowid',        -- messages の rowid を使う
  tokenize='unicode61'
);

-- INSERT同期：追加時にFTSへ反映
CREATE TRIGGER messages_ai AFTER INSERT ON messages
BEGIN
  INSERT INTO messages_fts(rowid, content, item_id)
  VALUES (new.rowid, new.content, new.item_id);
END;

-- DELETE同期：削除時は rowid だけで“delete”特殊挿入（安全）
CREATE TRIGGER messages_ad AFTER DELETE ON messages
BEGIN
  INSERT INTO messages_fts(messages_fts, rowid)
  VALUES ('delete', old.rowid);
END;

-- UPDATE同期：旧rowidをdelete → 新内容をinsert
CREATE TRIGGER messages_au AFTER UPDATE ON messages
BEGIN
  INSERT INTO messages_fts(messages_fts, rowid) VALUES ('delete', old.rowid);
  INSERT INTO messages_fts(rowid, content, item_id)
  VALUES (new.rowid, new.content, new.item_id);
END;

-- ----------------------------
-- 商材（可変列はJSON）
-- ----------------------------
CREATE TABLE IF NOT EXISTS products (
  id          TEXT PRIMARY KEY,           -- 生成UUID or ハッシュ
  category    TEXT NOT NULL,              -- cpu, case-fan, keyboard等
  name        TEXT NOT NULL,
  price       REAL,
  specs_json  TEXT,                        -- 可変カラムをJSONで格納
  source_csv  TEXT NOT NULL                -- 元のCSVファイル名
);

CREATE INDEX IF NOT EXISTS idx_products_cat_name ON products(category, name);
CREATE INDEX IF NOT EXISTS idx_products_category ON products(category);

-- ----------------------------
-- 取引履歴（案件専用）
-- ----------------------------
CREATE TABLE IF NOT EXISTS history (
  item_id           TEXT NOT NULL REFERENCES items(id) ON DELETE CASCADE,
  id                TEXT NOT NULL,          -- CSVのUUID（取引ID）
  order_date        TEXT,                   -- 発注日
  delivery_date     TEXT,                   -- 納期
  invoice_date      TEXT,                   -- 請求日
  business_partners TEXT NOT NULL,          -- 取引先企業名
  category          TEXT,                   -- 商品カテゴリ
  product_name      TEXT,                   -- 商品名
  quantity          REAL,                   -- 数量
  unit_price        REAL,                   -- 単価
  amount            REAL,                   -- 総額
  PRIMARY KEY(item_id, id)                  -- 案件ごとの一意制約
);

CREATE INDEX IF NOT EXISTS idx_hist_item_date    ON history(item_id, order_date);
CREATE INDEX IF NOT EXISTS idx_hist_item_cat     ON history(item_id, category);
CREATE INDEX IF NOT EXISTS idx_hist_item_partner ON history(item_id, business_partners);

-- ----------------------------
-- 取引サマリビュー
-- ----------------------------
DROP VIEW IF EXISTS v_item_summary;
CREATE VIEW v_item_summary AS
SELECT 
  i.id            AS item_id,
  i.title,
  i.company_name,
  i.description,
  i.created_at,
  i.updated_at,
  COUNT(h.id)                       AS transaction_count,
  COALESCE(SUM(h.amount), 0)        AS total_amount,
  MAX(h.order_date)                 AS last_order_date,
  -- ユーザー送信のチャット回数
  (SELECT COUNT(*) FROM messages WHERE item_id = i.id AND role = 'user') AS user_message_count
FROM items i
LEFT JOIN history h ON i.id = h.item_id
GROUP BY i.id, i.title, i.company_name, i.description, i.created_at, i.updated_at;
