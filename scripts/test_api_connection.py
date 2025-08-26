#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
API接続とパラメータのテストスクリプト
"""

import os
import sys
from pathlib import Path

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 環境変数の読み込み
from dotenv import load_dotenv
load_dotenv()

from openai import AzureOpenAI

def test_azure_openai_connection():
    """Azure OpenAI接続のテスト"""
    print("=== Azure OpenAI接続テスト ===")
    
    # 環境変数の確認
    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    api_key = os.getenv("AZURE_OPENAI_API_KEY")
    api_version = os.getenv("API_VERSION", "2024-12-01-preview")
    
    print(f"エンドポイント: {endpoint}")
    print(f"APIキー: {'設定済み' if api_key else '未設定'}")
    print(f"APIバージョン: {api_version}")
    
    if not endpoint or not api_key:
        print("❌ 必要な環境変数が設定されていません")
        return False
    
    try:
        # クライアントの初期化
        client = AzureOpenAI(
            azure_endpoint=endpoint,
            api_key=api_key,
            api_version=api_version
        )
        print("✓ Azure OpenAI クライアント初期化完了")
        
        # 簡単なテストリクエスト
        print("簡単なテストリクエストを実行中...")
        response = client.chat.completions.create(
            model="gpt-5-mini",
            messages=[
                {"role": "system", "content": "あなたはテスト用のアシスタントです。"},
                {"role": "user", "content": "こんにちは"}
            ],
            max_completion_tokens=200
            # temperature=0.1 は GPT-5-mini でサポートされていないため削除
        )
        
        print(f"✓ API呼び出し成功: {response.choices[0].message.content}")
        print(f"使用トークン: {response.usage}")
        
        return True
        
    except Exception as e:
        print(f"❌ エラーが発生: {e}")
        error_msg = str(e)
        
        if "max_tokens" in error_msg:
            print("💡 ヒント: 'max_tokens' の代わりに 'max_completion_tokens' を使用してください")
        elif "400" in error_msg:
            print("💡 ヒント: APIリクエストのパラメータを確認してください")
        elif "401" in error_msg:
            print("💡 ヒント: APIキーが正しく設定されているか確認してください")
        elif "404" in error_msg:
            print("💡 ヒント: モデル名またはエンドポイントが正しいか確認してください")
        
        return False

def test_tavily_connection():
    """TAVILY API接続のテスト"""
    print("\n=== TAVILY API接続テスト ===")
    
    api_key = os.getenv("TAVILY_API_KEY")
    print(f"TAVILY APIキー: {'設定済み' if api_key else '未設定'}")
    
    if not api_key:
        print("❌ TAVILY APIキーが設定されていません")
        return False
    
    try:
        from tavily import TavilyClient
        client = TavilyClient(api_key=api_key)
        print("✓ TAVILY クライアント初期化完了")
        
        # 簡単なテスト検索
        print("簡単なテスト検索を実行中...")
        response = client.search(
            query="テスト",
            search_depth="basic",
            max_results=1
        )
        
        print(f"✓ 検索成功: {len(response.get('results', []))}件の結果")
        return True
        
    except Exception as e:
        print(f"❌ エラーが発生: {e}")
        return False

def main():
    """メイン処理"""
    print("API接続テストを開始...")
    
    # Azure OpenAI テスト
    azure_success = test_azure_openai_connection()
    
    # TAVILY API テスト
    tavily_success = test_tavily_connection()
    
    print("\n=== テスト結果 ===")
    print(f"Azure OpenAI: {'✅ 成功' if azure_success else '❌ 失敗'}")
    print(f"TAVILY API: {'✅ 成功' if tavily_success else '❌ 失敗'}")
    
    if azure_success and tavily_success:
        print("\n🎉 すべてのAPI接続テストが成功しました！")
        return True
    else:
        print("\n⚠️ 一部のAPI接続テストが失敗しました。設定を確認してください。")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
