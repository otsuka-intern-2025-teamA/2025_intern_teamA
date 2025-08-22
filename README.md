# otsuka_internship_teamA
営業支援システム - 企業分析とRAG検索機能を持つStreamlit + FastAPIアプリケーション

## 概要
案件ごとに分離されたデータベース設計により、企業分析と提案書生成を行うシステムです。
企業分析フローでは、過去の会話履歴・取引履歴・商材情報を統合してRAG処理を行います。

## members
- アキモヴ・ダニラ
- 吉川泰生
- 柴崎陸
- 深瀬智大

## 仮想環境作成方法
1. cd ~~\otsuka_internship_teamA
2. python -m venv .venv
3. .venv\Scripts\activate
4. pip install jupyter ipykernel
5. python -m ipykernel install --user --name otsuka-env --display-name "Python (otsuka-env)"
6. pip install -r requirements.txt

## プロジェクト構成
ファイル名については適当です。

```
otsuka_internship_teamA/
├── apps/                           # アプリケーション
│   ├── streamlit/                  # フロントエンド（Streamlit）
│   │   ├── app.py                  # エントリーポイント（案件ホーム + 右ペイン遷移）
│   │   ├── pages/                  # Streamlit公式のマルチページ
│   │   │   ├── 1_案件一覧.py
│   │   │   ├── 2_企業を知る.py      # 企業分析チャット（RAG UI）
│   │   │   └── 3_提案を作る.py      # PPT生成フォーム
│   │   ├── components/             # UI部品
│   │   │   ├── case_card.py        # 案件カード表示
│   │   │   ├── right_pane.py       # 右ペイン管理
│   │   │   └── chat_panel.py       # チャットパネル
│   │   ├── .streamlit/config.toml  # Streamlit設定
│   │   └── requirements.txt        # 依存関係
│   │
│   └── fastapi/                    # バックエンド（FastAPI）
│       ├── app/
│       │   ├── main.py             # FastAPIエントリーポイント
│       │   ├── api/
│       │   │   ├── routers/        # APIルーター
│       │   │   │   ├── cases.py    # 案件CRUD API
│       │   │   │   ├── messages.py # メッセージAPI
│       │   │   │   ├── analysis.py # RAG検索・企業分析API
│       │   │   │   └── proposal.py # 提案書生成API
│       │   │   └── deps.py         # 依存性注入
│       │   ├── db/
│       │   │   ├── session.py      # データベース接続
│       │   │   ├── models.py       # SQLAlchemyモデル
│       │   │   └── init_db.py      # DB初期化・シード投入
│       │   ├── schemas/            # （削除済み - シンプルなdict形式APIに変更）
│       │   ├── services/           # ビジネスロジック
│       │   │   ├── rag_retriever.py # FTS5検索・RAG機能
│       │   │   ├── tx_summary.py   # 取引集計・サマリー
│       │   │   └── ppt_builder.py  # PowerPoint生成
│       │   └── core/
│       │       ├── config.py       # 設定管理
│       │       └── logging.py      # ログ設定
│       └── requirements.txt
│
├── data/                           # データファイル
│   ├── sqlite/                     # SQLiteデータベース
│   │   └── app.db                  # メインDB（自動生成）
│   ├── ddl/                        # データベース定義
│   │   ├── schema.sql              # テーブル定義・FTS5設定（実装済み）
│   │   └── seed.sql                # 初期データ（未実装）
│   ├── csv/                        # CSVデータ
│   │   ├── products/               # 商材データ
│   │   │   ├── DatasetA/           # 基本PC部品データ
│   │   │   │   ├── cpu.csv
│   │   │   │   ├── keyboard.csv
│   │   │   │   ├── headphones.csv
│   │   │   │   └── ...（9ファイル）
│   │   │   ├── DatasetB/           # 詳細部品・ラップトップデータ
│   │   │   │   ├── laptop_dataset_cleaned_full.csv
│   │   │   │   ├── memory.csv
│   │   │   │   ├── monitor.csv
│   │   │   │   └── ...（17ファイル）
│   │   │   └── trade_history_dummy_100.csv  # 取引履歴サンプル
│   │   └── templates/
│   │       └── proposal_template.pptx  # PPT雛形
│   ├── DatasetA.ipynb              # データ分析用ノートブック
│   ├── DatasetB.ipynb              # データ分析用ノートブック
│   └── gpt_call_template.ipynb     # OpenAI API呼び出し例
├── scripts/                        # データローダー・ユーティリティ
│   ├── load_products.py            # 商材データロード（実装済み）
│   ├── load_history.py             # 取引履歴ロード（実装済み）
│   ├── dev_up.sh                   # 開発環境起動
│   └── check_fts.sql               # FTS5動作確認
├── README.md
└── requirements.txt                # ルート依存関係
```

## 主要機能

### 1. 案件管理（実装済み）
- 案件カードによる視覚的な案件管理
- 案件のCRUD操作（シンプルなdict形式API）
- 案件ごとのデータ分離設計

### 2. 企業分析フロー（実装済み）
- **データ収集**: 過去会話履歴 + 取引履歴 + 商材情報
- **FTS5全文検索**: 高速メッセージ検索
- **案件境界**: item_idによる完全データ分離
- **RAG処理**: コンテキスト統合による企業分析
- **チャット形式**: 質問→データ収集→AI分析→保存

### 3. 提案書生成（未実装）
- 分析結果を基にしたPowerPoint提案書の自動生成
- テンプレートベースの資料作成

## 技術スタック

- **フロントエンド**: Streamlit
- **バックエンド**: FastAPI（シンプルなdict形式API）
- **データベース**: SQLite + FTS5（全文検索）
- **ORM**: SQLAlchemy
- **AI/ML**: OpenAI API (Azure) ※モック実装済み
- **データ処理**: pandas, numpy

## データベース設計

### 案件境界による分離設計
```
items (案件)
├── messages (会話履歴) ← item_id で分離
└── history (取引履歴)  ← item_id で分離

products (商材マスタ) ← 全案件共通
```

### 企業分析フロー
```
1. 質問受信 → 2. データ収集 → 3. AI分析 → 4. 結果保存
     ↓             ↓            ↓          ↓
   API入力     FTS5検索      LLM処理    messages保存
              取引履歴      （モック）   sources記録
              商材情報
```

## セットアップ手順

### 1. 環境構築
```bash
cd otsuka_internship_teamA
python -m venv .venv
.venv\Scripts\activate  # Windows
pip install -r requirements.txt
```

### 2. データベース初期化
```bash
# 商材データをロード
python scripts/load_products.py --replace

# 取引履歴をロード（案件ごと）
python scripts/load_history.py --item <ITEM_ID> --company "企業名"
```

### 3. API起動
```bash
cd apps/fastapi
uvicorn app.main:app --reload
```

### 4. フロントエンド起動
```bash
cd apps/streamlit
streamlit run app.py
```

## API仕様（シンプル版）

### 案件API
```python
GET  /items                    # 案件一覧（サマリ付き）
GET  /items/{item_id}         # 案件詳細
POST /items                   # 案件作成
PUT  /items/{item_id}         # 案件更新
```

### 企業分析API
```python
POST /analysis/query          # 企業分析実行
# 入力: {"item_id": "...", "question": "...", "company_name": "..."}
# 出力: {"result": "分析結果", "context_summary": "...", "sources_used": [...]}

POST /analysis/history/load   # 取引履歴ロード
# 入力: {"item_id": "...", "company_name": "..."}
```

### メッセージAPI
```python
GET  /items/{item_id}/messages        # 会話履歴取得
POST /items/{item_id}/messages        # メッセージ追加
GET  /items/{item_id}/messages/search # FTS5検索
```
