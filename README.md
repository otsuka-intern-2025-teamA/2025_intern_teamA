# otsuka_internship

営業支援システム - 企業分析とRAG検索機能を持つStreamlit + FastAPIアプリケーション

## member
- アキモウダニラ
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
│       │   ├── schemas/            # Pydantic DTO
│       │   │   ├── cases.py
│       │   │   ├── messages.py
│       │   │   └── analysis.py
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
│   │   └── app.db                  # メインDB
│   ├── ddl/                        # データベース定義
│   │   ├── schema.sql              # テーブル定義・FTS5設定
│   │   └── seed.sql                # 初期データ
│   ├── csv/                        # CSVデータ
│   │   ├── DatasetA/               # 基本PC部品データ
│   │   │   ├── cpu.csv
│   │   │   ├── keyboard.csv
│   │   │   ├── headphones.csv
│   │   │   └── ...（9ファイル）
│   │   └── DatasetB/               # 詳細部品・ラップトップデータ
│   │       ├── laptop_dataset_cleaned_full.csv
│   │       ├── memory.csv
│   │       ├── monitor.csv
│   │       └── ...（17ファイル）
│   ├── templates/
│   │   └── proposal_template.pptx  # PPT雛形
│   ├── DatasetA.ipynb              # データ分析用ノートブック
│   ├── DatasetB.ipynb              # データ分析用ノートブック
│   └── gpt_call_template.ipynb     # OpenAI API呼び出し例
│
├── .env.example                    # 環境変数サンプル
├── README.md
└── requirements.txt                # ルート依存関係
```

## 主要機能

### 1. 案件管理
- 案件カードプールによる視覚的な案件管理
- 案件のCRUD操作
- 案件ステータス管理

### 2. 企業分析チャット（RAG）
- FTS5全文検索による商品データ検索
- OpenAI APIを使用した企業分析
- 取引履歴の集計・サマリー生成
- インタラクティブなチャットUI

### 3. 提案書生成
- 分析結果を基にしたPowerPoint提案書の自動生成
- テンプレートベースの資料作成

## 技術スタック

- **フロントエンド**: Streamlit
- **バックエンド**: FastAPI
- **データベース**: SQLite + FTS5（全文検索）
- **AI/ML**: OpenAI API (Azure)
- **データ処理**: pandas, numpy
- **文書生成**: python-pptx

## データフロー

```
CSV生データ → SQLite取込 → FTS5検索 → RAG分析 → LLM処理 → PPT生成
     ↑              ↑             ↑           ↑          ↑
   DatasetA/B    data/sqlite/  analysis.py  OpenAI   templates/
```
