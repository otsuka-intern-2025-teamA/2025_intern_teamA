# AIプレゼンテーション生成機能 ユーザーガイド

## 概要
この機能は、AIエージェントが企業情報、商談詳細、製品候補を基に自動的にプレゼンテーションPPTXを生成するものです。

## 前提条件
- `.env`ファイルに以下のAPIキーが設定されていること：
  - `AZURE_OPENAI_ENDPOINT`
  - `AZURE_OPENAI_API_KEY`
  - `TAVILY_API_KEY`

## 使用方法

### 1. 案件選択
- 案件一覧から対象企業を選択
- 「スライド生成」ボタンをクリック

### 2. 商談詳細入力
- 「商談の詳細」テキストエリアに商談内容を入力
- 参考資料があればアップロード（任意）

### 3. 製品候補取得
- 「候補を取得」ボタンをクリック
- AIが製品候補を分析・選定
- 候補カードが表示される

### 4. AI設定調整
サイドバーの「AI設定」セクションで以下を調整：

#### GPT API使用
- ✅ チェック：GPT-5-miniによる企業課題分析と製品情報要約
- ❌ 未チェック：デフォルトテキスト「あいうえお」を使用

#### TAVILY API使用
- ✅ チェック：TAVILY APIによる製品情報のウェブ検索
- ❌ 未チェック：デフォルトテキスト「あいうえお」を使用

#### TAVILY API呼び出し回数
- 各製品に対してTAVILY APIを何回呼び出すかを指定（1-5回）
- 回数が多いほど詳細な情報が取得できるが、処理時間が長くなる

### 5. プレゼンテーション生成
- 「生成」ボタンをクリック
- AIエージェントが以下の処理を実行：
  1. 企業課題の分析
  2. 製品情報の検索・要約
  3. スライドの自動作成
  4. ロゴの配置

### 6. ダウンロード
- 生成完了後、ダウンロードボタンが表示
- PPTXファイルをローカルに保存

## 生成されるスライド構成

### 1. タイトルスライド
- 企業名
- 作成日
- Otsukaロゴ

### 2. 現状の課題
- AI分析による課題の整理（3-5点）
- 具体的で解決可能な内容

### 3. 製品提案スライド（製品数分）
各製品について：
- 製品名と画像
- ご提案機器について
- 主な特徴
- 導入メリット
- 価格情報

### 4. 総コスト
- 全提案の投資額サマリー
- 税抜き表示
- 補足情報

## 注意事項

### API使用制限
- TAVILY API：製品あたり指定回数まで
- GPT API：企業課題分析と製品情報要約に使用

### データ処理
- **NaN値**: 製品価格のNaN値は「要お見積もり」として表示
- **不完全データ**: データが不完全でもプレゼンテーション生成が可能
- **エラー処理**: 各段階でエラーが発生した場合のフォールバック処理

### フォールバック
- APIが使用できない場合、デフォルトテキスト「あいうえお」を使用
- エラーが発生した場合、下書きのみ作成される

### 画像
- 製品画像：`data/images/example_picture.png`を使用
- ロゴ：`data/images/otsuka_logo.jpg`を使用（アスペクト比保持）

## トラブルシューティング

### よくある問題

#### 1. APIエラー
- `.env`ファイルの設定を確認
- APIキーの有効性を確認
- ネットワーク接続を確認
- **GPT-5-miniエラー**: `max_tokens`パラメータエラーは修正済み
- **API接続テスト**: `scripts/test_api_connection.py`で接続状況を確認

#### 2. プレゼンテーション生成失敗
- 製品候補が取得されているか確認
- 企業名が正しく設定されているか確認
- エラーメッセージを確認

#### 3. NaN値エラー
- **解決済み**: 製品価格のNaN値は自動的に「要お見積もり」として処理
- データの整合性を確認
- 必要に応じて製品情報を更新

#### 4. 画像が表示されない
- 画像ファイルの存在を確認
- ファイルパスの権限を確認

### ログ確認
- Streamlitのコンソール出力を確認
- エラーメッセージの詳細を確認

## カスタマイズ

### スライドテンプレート
- `apps/streamlit/lib/slide_generator.py`を編集
- スライドレイアウトやデザインを変更

### デフォルトテキスト
- `slide_generator.py`の`search_product_info`メソッドを編集
- フォールバック時のテキストを変更

### ロゴ配置
- `slide_generator.py`の各`_create_*_slide`メソッドを編集
- ロゴの位置やサイズを調整

## サポート

問題が発生した場合：
1. エラーメッセージを確認
2. ログを確認
3. 設定を確認
4. 必要に応じて開発チームに連絡

## よくある問題と解決策

### GPT-5-mini の `max_tokens` エラー
**問題**: "Unsupported parameter: 'max_tokens' is not supported with this model"
**解決策**: ✅ 修正済み - `max_completion_tokens` を使用

### GPT-5-mini の `temperature` エラー
**問題**: "Unsupported value: 'temperature' does not support 0.3 with this model. Only the default (1) value is supported."
**解決策**: ✅ 修正済み - `temperature` パラメータを削除（デフォルト値1を使用）

### Tuple Index エラー
**問題**: "tuple index out of range"
**解決策**: ✅ 修正済み - テキスト処理時のインデックスチェックを追加

### トークン制限エラー
**問題**: "Could not finish the message because max_tokens or model output limit was reached"
**解決策**: ✅ 修正済み - `max_completion_tokens`を2000に増加、環境変数で設定可能

### API接続の確認
```bash
# API接続テストの実行
python scripts/test_api_connection.py
```

### 環境変数の確認
`.env`ファイルに以下が設定されているか確認：
```bash
AZURE_OPENAI_ENDPOINT=https://lab-teama.openai.azure.com/
AZURE_OPENAI_API_KEY=your_api_key_here
TAVILY_API_KEY=your_tavily_key_here
API_VERSION=2024-12-01-preview
MAX_COMPLETION_TOKENS=2000
```

**トークン設定の説明:**
- `MAX_COMPLETION_TOKENS`: GPT-5-miniの最大出力トークン数（デフォルト: 2000）
- より長い回答が必要な場合は値を増やしてください（例: 4000, 8000）
- 値が大きいほど処理時間が長くなります
