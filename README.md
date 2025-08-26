# 案件管理システム + AIプレゼンテーション生成

企業分析機能付きの案件管理システムです。SQLiteデータベースとLLM（Large Language Model）を活用し、効率的な企業分析とデータ管理を実現します。さらに、AIエージェントによる自動プレゼンテーション生成機能を搭載し、営業活動を強力にサポートします。

## 🛠️ 技術構成

- **フロントエンド**: Streamlit
- **バックエンド**: FastAPI
- **データベース**: SQLite（単一ファイル）
- **データソース**: CSV（商材データ、取引履歴）
- **AI機能**: OpenAI GPT / Azure OpenAI
- **検索機能**: FTS5（全文検索）
- **プレゼンテーション生成**: python-pptx
- **Web検索**: Tavily API

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
│       ├── slide_generation_module.py  # スライド生成モジュール
│       └── lib/
│           ├── api.py             # FastAPI通信ライブラリ
│           ├── styles.py          # 共通スタイル定義
│           ├── slide_generator.py # AIスライド生成エージェント
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
│   ├── check_db.py               # データベース内容確認ツール
│   └── test_slide_generator.py   # スライド生成テストスクリプト
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

## 🤖 AIプレゼンテーション生成機能

### 概要
営業担当者向けのAIエージェントが、企業レポート、商品提案、ユーザー入力に基づいて自動的にPPTXプレゼンテーションを生成します。

### 主要機能
- **自動スライド生成**: LLMによる提案内容を基にした構造化されたプレゼンテーション
- **Web検索連携**: Tavily APIによる商品情報の強化
- **動的コスト計算**: リアルタイムでのコスト比較とROI分析
- **カスタマイズ可能**: ユーザー指示による柔軟な内容調整

### スライド構成
1. **現状の課題** - 企業が抱える問題点の分析
2. **ご提案機器** - 各商品の詳細説明（個別スライド）
3. **導入メリット** - 各商品後の効果説明
4. **トータルコスト** - 総費用と導入スケジュール
5. **トータルコスト比較** - 現状 vs 提案の詳細比較

### 技術的特徴
- **python-pptx**: プロフェッショナルなPPTX生成
- **Azure OpenAI**: GPT-5-miniによる高品質な内容生成
- **Tavily API**: 最新の商品情報と市場データ
- **画像処理**: ロゴと商品画像の適切な配置
- **レスポンシブデザイン**: 16:9比率での最適化

## 🚀 セットアップ・実行手順

### 1. 環境変数の設定

`.env`ファイルを作成し、以下のAPIキーを設定してください：

```bash
# Azure OpenAI設定
AZURE_OPENAI_ENDPOINT=https://your-endpoint.openai.azure.com/
AZURE_OPENAI_API_KEY=your-api-key
AZURE_OPENAI_EMBED_DEPLOYMENT=gpt-5-mini

# Tavily API設定
TAVILY_API_KEY=your-tavily-api-key
```

### 2. 仮想環境の準備

```bash
# 仮想環境をアクティベート
source venv/bin/activate  # macOS/Linux
# または
.venv\Scripts\activate    # Windows

# 必要なパッケージをインストール
pip install -r requirements.txt
```

### 3. アプリケーションの起動

**2つのターミナルで同時に起動してください：**

#### ターミナル1: FastAPIサーバー
```bash
source venv/bin/activate  # macOS/Linux
# または
.venv\Scripts\activate    # Windows
cd apps/fastapi
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

#### ターミナル2: Streamlitアプリ
```bash
source venv/bin/activate  # macOS/Linux
# または
.venv\Scripts\activate    # Windows
cd apps/streamlit
streamlit run app.py
```

### 4. アクセス

- **メインアプリ**: http://localhost:8501
- **API管理画面**: http://localhost:8000/docs
- **スライド生成**: メインアプリ内の「スライド生成」タブ

## 📊 データ管理

### データベース内容の確認

```bash
# 基本的な確認（サンプルデータ表示）
python scripts/check_db.py

# 全てのデータを表示
python scripts/check_db.py --all
```

### スライド生成のテスト

```bash
# スライド生成機能のテスト
python scripts/test_slide_generator.py
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

## 🎯 使用方法

### スライド生成の手順

1. **案件選択**: メインアプリで対象案件を選択
2. **スライド生成タブ**: 「スライド生成」タブに移動
3. **設定調整**: 
   - `use_tavily_api`: Tavily APIの使用有無
   - `use_gpt_api`: GPT APIの使用有無
   - `tavily_uses`: 各商品に対するTavily検索回数
4. **追加指示**: プレゼンテーションのカスタマイズ指示を入力
5. **生成実行**: 「プレゼンテーション生成」ボタンをクリック
6. **ダウンロード**: 生成されたPPTXファイルをダウンロード

### カスタマイズオプション

- **API使用制御**: 各APIの使用/不使用を個別に制御
- **デフォルトテキスト**: API不使用時は「あいうえお」を自動挿入
- **動的コスト計算**: LLM提案に基づくリアルタイムコスト分析
- **画像配置**: ロゴと商品画像の自動配置（アスペクト比保持）

## 🚨 トラブルシューティング

### よくある問題

1. **APIキーエラー**: `.env`ファイルの設定を確認
2. **依存関係エラー**: `pip install -r requirements.txt`を実行
3. **画像読み込みエラー**: `data/images/`フォルダの存在確認
4. **メモリ不足**: 大きなプレゼンテーション生成時は仮想環境のメモリ制限を調整

### ログ確認

```bash
# Streamlitログの確認
streamlit run app.py --logger.level debug

# FastAPIログの確認
uvicorn app.main:app --log-level debug

## 🛠️ 開発ガイドライン

### コードスタイル
- **Python**: PEP 8準拠
- **コメント**: 日本語での詳細な説明
- **エラーハンドリング**: 適切な例外処理とユーザーフレンドリーなメッセージ
- **ログ**: デバッグ情報の適切な出力

### 新機能追加時の注意点
1. **依存関係**: `requirements.txt`の更新
2. **環境変数**: `.env`ファイルの設定例追加
3. **テスト**: 新機能の動作確認スクリプト作成
4. **ドキュメント**: README.mdの更新

### 画像ファイルの管理
- **ロゴ**: `data/images/otsuka_logo.jpg` - アスペクト比保持
- **商品画像**: `data/images/example_picture.png` - プレースホルダー
- **サイズ制限**: プレゼンテーション境界内での配置

## 📝 ライセンス

このプロジェクトは大塚製薬のインターンシップ用に開発されたものです。

## 🤝 コントリビューション

開発チームAのメンバーによる共同開発プロジェクトです。

---

**最終更新**: 2025年1月
**バージョン**: 2.0.0 (AIプレゼンテーション生成機能追加)
