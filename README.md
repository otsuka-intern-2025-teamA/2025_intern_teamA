# 案件管理システム

企業分析機能付きの案件管理システムです。SQLiteデータベースとLLM（Large Language Model）を活用し、効率的な企業分析とデータ管理を実現します。

## 🛠️ 技術構成

- **フロントエンド**: Streamlit
- **バックエンド**: FastAPI
- **データベース**: SQLite（単一ファイル）
- **データソース**: CSV（商材データ、取引履歴）
- **AI機能**: OpenAI GPT / Azure OpenAI GPT-5-mini
- **検索機能**: FTS5（全文検索）、TAVILY API（ウェブ検索）
- **プレゼンテーション**: python-pptx（PPTX生成）

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
│   │   └── products/
│   │       ├── DatasetA/          # 商材データセットA（空）
│   │       ├── DatasetB/          # 商材データセットB（空）
│   │       └── history.csv  # サンプル取引履歴
│   ├── images/                    # アプリ画像
│   │   ├── otsuka_icon.png       # アプリアイコン
│   │   └── otsuka_logo.jpg       # ロゴ画像
│   ├── templates/                 # テンプレートファイル
│   │   └── proposal_template.pptx # 提案書テンプレート
│   └── sqlite/
│       └── app.db                 # SQLiteデータベース（Git追跡外）
├── scripts/                       # データ管理スクリプト
│   └── check_db.py               # データベース内容確認ツール
└── requirements.txt               # Python依存関係
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
- **AI提案**: LLMによる製品候補の選定と要約
- **プレゼンテーション生成**: AIエージェントによる自動PPTX生成
- **ウェブ検索**: TAVILY APIによる製品情報の最新化

## 🚀 セットアップ・実行手順

### 1. 仮想環境の準備

```powershell
# 仮想環境をアクティベート
.venv\Scripts\activate

# 必要なパッケージをインストール
pip install -r requirements.txt
```

**新機能の追加依存関係:**
- `python-pptx`: PPTXプレゼンテーション生成
- `tavily-python`: TAVILY API ウェブ検索

### 2. アプリケーションの起動

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

## 🎯 新機能: AIプレゼンテーション生成

### 概要
AIエージェントが企業情報、商談詳細、製品候補を基に自動的にプレゼンテーションPPTXを生成します。

### 最近の修正
- **NaN値処理**: 製品価格のNaN値を適切に処理し、「要お見積もり」として表示
- **エラーハンドリング**: データ不整合時のフォールバック処理を追加
- **堅牢性向上**: 不完全なデータでもプレゼンテーション生成が可能
- **APIパラメータ修正**: GPT-5-mini用に`max_completion_tokens`を使用
- **Temperature制限対応**: GPT-5-miniでサポートされていない`temperature`パラメータを削除
- **Tuple Index修正**: テキスト処理時のインデックスエラーを修正
- **トークン制限対応**: `max_completion_tokens`を2000に増加し、設定可能に
- **プレゼンテーション形式修正**: 要件に合わせたスライド構成とレイアウトに変更
- **通貨表示変更**: 円からドル表示に変更
- **エラー診断改善**: より詳細なエラーメッセージと解決策の提示

### 主な機能
- **企業課題分析**: GPT-5-miniによる現状課題の自動分析
- **製品情報検索**: TAVILY APIによる最新製品情報の取得
- **自動スライド生成**: 構造化されたプレゼンテーションの自動作成
- **ロゴ統合**: Otsukaロゴの自動配置（アスペクト比保持）

### スライド構成
1. **タイトルスライド**: 案件名 + 企業名、作成日、ロゴ
2. **現状の課題**: AI分析による課題の整理
3. **製品提案スライド**: 各製品を個別スライドに（ご提案機器について、導入メリット、画像、価格）
4. **総コスト**: 全提案の投資額サマリー（ドル表示）

### 設定オプション
- `use_gpt_api`: GPT-5-miniによる分析の有効/無効
- `use_tavily_api`: TAVILY API検索の有効/無効  
- `tavily_uses`: 製品あたりのAPI呼び出し回数（1-5回）

### 使用方法
1. 案件一覧から対象企業を選択
2. 「スライド生成」ページに移動
3. 商談詳細を入力
4. 「候補を取得」で製品候補を検索
5. AI設定を調整
6. 「生成」ボタンでプレゼンテーション作成
7. ダウンロードボタンでPPTXファイルを取得
