# 案件管理システム

企業分析機能付きの案件管理システムです。SQLiteデータベースとLLM（Large Language Model）を活用し、効率的な企業分析とデータ管理を実現します。

## 🛠️ 技術構成

- **フロントエンド**: Streamlit
- **バックエンド**: FastAPI
- **データベース**: SQLite（単一ファイル）
- **データソース**: CSV（商材データ、取引履歴）
- **AI機能**: OpenAI GPT / Azure OpenAI
- **検索機能**: FTS5（全文検索）

## 📁 プロジェクト構成

```
otsuka_internship_teamA/
├── apps/
│   ├── fastapi/                    # バックエンドAPI
│   │   └── app/
│   │       ├── main.py            # FastAPIメインアプリ
│   │       ├── api/routers/       # APIエンドポイント
│   │       │   ├── cases.py       # 案件CRUD API
│   │       │   ├── analysis.py    # 企業分析API
│   │       │   └── messages.py    # メッセージ管理API
│   │       └── db/                # データベース関連
│   │           ├── models.py      # SQLAlchemyモデル
│   │           └── session.py     # DB接続・初期化設定
│   └── streamlit/                 # フロントエンドアプリ
│       ├── app.py                 # メインアプリ（案件管理）
│       ├── company_analysis_module.py  # 企業分析モジュール
│       └── lib/
│           ├── api.py             # FastAPI通信ライブラリ
│           ├── styles.py          # 共通スタイル定義
│           └── company_analysis/  # 企業分析機能
│               ├── config.py      # 設定管理（APIキー等）
│               ├── data.py        # データ構造定義
│               ├── llm.py         # LLM連携処理
│               └── ui.py          # 企業分析UI
├── data/
│   ├── ddl/
│   │   └── schema.sql             # データベーススキーマ
│   ├── csv/                       # CSVデータ（商材・取引履歴）
│   │   ├── products/
│   │   │   ├── DatasetA/         # 商材データセットA
│   │   │   └── DatasetB/         # 商材データセットB
│   │   └── trade_history_dummy_100.csv  # サンプル取引履歴
│   ├── images/                    # アプリ画像
│   │   ├── otsuka_icon.png       # アプリアイコン
│   │   └── otsuka_logo.jpg       # ロゴ画像
│   ├── templates/                 # テンプレートファイル
│   │   └── proposal_template.pptx # 提案書テンプレート
│   └── sqlite/
│       └── app.db                 # SQLiteデータベース
└── scripts/
    ├── load_products.py           # 商材データローダー
    └── load_history.py            # 取引履歴ローダー
```

## 🗄️ データベーススキーマ

### テーブル構成

1. **items** - 案件（カード）管理
2. **messages** - 案件内の会話ログ
3. **messages_fts** - メッセージの全文検索（FTS5）
4. **products** - 商材データ（DatasetA/B統合）
5. **history** - 取引履歴（案件ごとに管理）

### 主要機能

- **案件ごとの分離**: 取引履歴は案件IDで完全分離
- **全文検索**: FTS5による高速メッセージ検索
- **JSON格納**: 可変構造データをJSON形式で柔軟に保存

## 🚀 セットアップ・実行手順

### 1. 仮想環境の準備

```powershell
# 仮想環境をアクティベート
.venv\Scripts\activate

# 必要なパッケージをインストール
pip install -r requirements.txt
```

### 2. データベースの初期化

```powershell
# 商材データをロード
python scripts/load_products.py --replace
```

### 3. アプリケーションの起動

**2つのターミナルで同時に起動してください：**

#### ターミナル1: FastAPIサーバー
```powershell
.venv\Scripts\activate
sorce .venv/bin/activate
cd apps\fastapi
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

#### ターミナル2: Streamlitアプリ
```powershell
.venv\Scripts\activate
sorce .venv/bin/activate
streamlit run apps\streamlit\app.py
```

### 4. アクセス

- **メインアプリ**: http://localhost:8501
- **API管理画面**: http://localhost:8000/docs

## 📊 データ管理

### 商材データのロード

```powershell
# 全商材データを更新
python scripts/load_products.py --replace

# 商材データを追加更新
python scripts/load_products.py --update
```

### 取引履歴のロード

```powershell
# 特定案件に取引履歴をロード
python scripts/load_history.py --item <案件ID> --company "企業名"

# 例：案件Aに株式会社〇〇の取引履歴をロード
python scripts/load_history.py --item 3838d414-5018-4648-904f-37fd18902bde --company "株式会社〇〇"
```

案件IDの確認方法：
```powershell
python -c "import sqlite3; conn = sqlite3.connect('data/sqlite/app.db'); cursor = conn.cursor(); cursor.execute('SELECT id, title, company_name FROM items'); print(cursor.fetchall()); conn.close()"
```

## 🔧 API仕様

### 案件管理API

- `GET /items/` - 案件一覧取得（サマリ付き）
- `GET /items/{item_id}` - 案件詳細取得
- `POST /items/` - 新規案件作成
- `PUT /items/{item_id}` - 案件更新
- `DELETE /items/{item_id}` - 案件削除

### メッセージ管理API

- `GET /items/{item_id}/messages/` - メッセージ一覧取得
- `POST /items/{item_id}/messages/` - メッセージ作成
- `GET /items/{item_id}/messages/?search=<query>` - FTS検索

### 企業分析API

- `POST /analysis/query` - 企業分析実行
- `POST /analysis/history/load` - 取引履歴ロード

## 🔍 データベース内容確認

### 案件データの確認

```powershell
# 案件詳細（フル情報）
python -c "import sqlite3; conn=sqlite3.connect('data/sqlite/app.db'); cursor=conn.cursor(); cursor.execute('SELECT * FROM items'); items=cursor.fetchall(); print('案件詳細:'); [print(f'ID:{item[0][:8]}... | {item[1]} | {item[2]} | {item[4]}') for item in items]; conn.close()"
```