# 新しいスライド生成システム

## 概要

このシステムは、AIエージェントを使用してPPTXテンプレートから自動的にプレゼンテーションを生成する新しいアーキテクチャです。

## アーキテクチャ

### 1. AIエージェント (`ai_agent.py`)
- **目的**: プレゼンテーション変数の自動生成
- **機能**:
  - 企業情報の分析
  - 製品選択理由の生成
  - 問題仮説の分析
  - 提案サマリーの作成
  - スケジュール計画の生成
  - 次のアクションの提案

### 2. テンプレートプロセッサ (`template_processor.py`)
- **目的**: PPTXテンプレートの処理と変数置換
- **機能**:
  - テンプレートのコピー作成
  - 変数の置換（フォーマット保持）
  - テキスト、テーブル、グループ化されたシェイプの処理

### 3. 新しいスライド生成器 (`new_slide_generator.py`)
- **目的**: 全体の統合とプレゼンテーション生成の管理
- **機能**:
  - AIエージェントとテンプレートプロセッサの統合
  - 変数の生成とテンプレート処理の調整
  - 最終的なPPTXファイルの生成

## 生成される変数

### 基本変数
- `{{PROJECT_NAME}}` - 案件名
- `{{COMPANY_NAME}}` - 取引先企業名

### 企業分析変数
- `{{CHAT_HISTORY_SUMMARY}}` - チャット履歴サマリー
- `{{PROBLEM_HYPOTHESES}}` - 問題仮説
- `{{PROPOSAL_SUMMARY}}` - 提案サマリー

### 製品変数（動的生成）
- `{{PRODUCTS[i].NAME}}` - 製品名
- `{{PRODUCTS[i].CATEGORY}}` - 製品カテゴリ
- `{{PRODUCTS[i].PRICE}}` - 製品価格（ドル表示）
- `{{PRODUCTS[i].REASON}}` - 製品選択理由

### 提案変数
- `{{EXPECTED_IMPACTS}}` - 期待される効果
- `{{TOTAL_COSTS}}` - 総コスト
- `{{SCHEDULE_PLAN}}` - スケジュール計画
- `{{NEXT_ACTIONS}}` - 次のアクション

### 構成変数
- `{{AGENDA_BULLETS}}` - アジェンダ（目次）

## 使用方法

### 1. 基本的な使用
```python
from lib.new_slide_generator import NewSlideGenerator

generator = NewSlideGenerator()
pptx_data = generator.create_presentation(
    project_name="案件名",
    company_name="企業名",
    meeting_notes="商談詳細",
    chat_history="チャット履歴",
    products=product_list,
    use_gpt=True,
    use_tavily=True,
    tavily_uses=2
)
```

### 2. 変数のプレビュー
```python
variables = generator.preview_variables(
    project_name="案件名",
    company_name="企業名",
    meeting_notes="商談詳細",
    chat_history="チャット履歴",
    products=product_list,
    use_gpt=False,  # API使用なし
    use_tavily=False
)
```

### 3. テンプレート情報の取得
```python
template_info = generator.get_template_info()
print(f"スライド数: {template_info['slide_count']}")
```

## API設定

### 必要な環境変数
```bash
# Azure OpenAI
AZURE_OPENAI_ENDPOINT=https://lab-teama.openai.azure.com/
AZURE_OPENAI_API_KEY=your_api_key_here
AZURE_OPENAI_EMBED_DEPLOYMENT=gpt-5-mini
API_VERSION=2024-12-01-preview

# TAVILY API
TAVILY_API_KEY=your_tavily_key_here

# トークン設定
MAX_COMPLETION_TOKENS=2000
```

## テンプレート要件

### PPTXファイル構造
- テンプレートファイル: `template/proposal_template.pptx`
- 変数は `{{VARIABLE_NAME}}` 形式で記述
- フォーマット（色、サイズ、フォント）は自動保持

### サポートされる要素
- テキストフレーム
- テーブル
- グループ化されたシェイプ
- タイトルスライド

## エラーハンドリング

### フォールバック処理
- API使用不可時: デフォルト値 "あいうえお" を使用
- テンプレートエラー: 適切なエラーメッセージを表示
- 変数生成失敗: 基本値のみでプレゼンテーション生成

### ログ出力
- 各段階での処理状況を詳細にログ出力
- エラー発生時の詳細情報を提供
- デバッグ用の情報表示

## テスト

### テストスクリプト
```bash
python scripts/test_new_system.py
```

### テスト内容
1. テンプレート情報の取得
2. 変数のプレビュー
3. AIエージェントのテスト
4. プレゼンテーション生成テスト

## 既存システムとの違い

### 従来のシステム
- スライドを一から作成
- 固定レイアウト
- 画像の手動配置

### 新しいシステム
- テンプレートベース
- 柔軟なレイアウト
- フォーマット保持
- AI駆動の内容生成

## 今後の拡張

### 計画されている機能
- 複数テンプレートのサポート
- カスタム変数の追加
- 画像の自動配置
- 多言語対応

### パフォーマンス改善
- バッチ処理の最適化
- キャッシュ機能の追加
- 非同期処理の実装
