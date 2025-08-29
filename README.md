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
│   │       ├── api/
│   │       │   ├── deps.py        # 依存関係管理
│   │       │   └── routers/       # APIエンドポイント
│   │       │       ├── cases.py       # 案件CRUD API
│   │       │       ├── analysis.py    # 企業分析API
│   │       │       └── messages.py    # メッセージ管理API
│   │       └── db/                # データベース関連
│   │           ├── models.py      # SQLAlchemyモデル
│   │           └── session.py     # DB接続・初期化設定
│   └── streamlit/                 # フロントエンドアプリ
│       ├── app.py                 # メインアプリ（案件管理）
│       ├── company_analysis_module.py  # 企業分析モジュール
│       ├── slide_generation_module.py  # スライド生成モジュール
│       └── lib/
│           ├── api.py             # FastAPI通信ライブラリ
│           ├── styles.py          # 共通スタイル定義
│           ├── ai_agent.py        # AIエージェント機能
│           ├── slide_generator.py # スライド生成エンジン
│           ├── new_slide_generator.py # 新スライド生成エンジン
│           ├── template_processor.py   # テンプレート処理
│           └── company_analysis/  # 企業分析機能
│               ├── config.py      # 設定管理（APIキー等）
│               ├── data.py        # データ構造定義
│               └── llm.py         # LLM連携処理
├── data/
│   ├── ddl/
│   │   └── schema.sql             # データベーススキーマ
│   ├── csv/                       # CSVデータ（商材・取引履歴）
│   │   └── products/
│   │       ├── DatasetA/          # 商材データセットA
│   │       ├── DatasetB/          # 商材データセットB（25カテゴリ）
│   │       │   ├── cpu.csv        # CPU（1,375件）
│   │       │   ├── memory.csv     # メモリ（12,601件）
│   │       │   ├── storage/       # ストレージ関連
│   │       │   ├── peripherals/   # 周辺機器
│   │       │   └── ...            # その他カテゴリ
│   │       └── history.csv        # 取引履歴（102件）
│   ├── images/                    # アプリ画像
│   │   ├── otsuka_icon.png       # アプリアイコン
│   │   └── otsuka_logo.jpg       # ロゴ画像
│   ├── template/                  # テンプレートファイル
│   └── sqlite/
│       └── app.db                 # SQLiteデータベース（Git追跡外）
├── scripts/                       # データ管理スクリプト
│   └── check_db.py               # データベース内容確認ツール
├── tools/                         # 開発・運用ツール
├── requirements.txt               # Python依存関係
├── pyproject.toml                # プロジェクト設定
├── SLIDE_GENERATION_GUIDE.md     # スライド生成機能ガイド
└── NEW_SLIDE_SYSTEM_README.md    # 新スライドシステム説明
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

### 2. アプリケーションの起動

**2つのターミナルで同時に起動してください：**

#### ターミナル1: FastAPIサーバー
```powershell
.venv\Scripts\activate
cd apps\fastapi
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

#### ターミナル2: Streamlitアプリ
```powershell
.venv\Scripts\activate
streamlit run apps\streamlit\app.py
```

### 3. アクセス

- **メインアプリ**: http://localhost:8501
- **API管理画面**: http://localhost:8000/docs

## 📊 データ管理

### データベース内容の確認

```bash
# 基本的な確認（サンプルデータ表示）
python scripts/check_db.py

# 全てのデータを表示
python scripts/check_db.py --all
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
