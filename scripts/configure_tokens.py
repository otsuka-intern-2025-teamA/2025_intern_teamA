#!/usr/bin/env python3
"""
トークン設定のヘルパースクリプト
"""

import os
from pathlib import Path


def configure_tokens():
    """トークン設定の確認と提案"""
    print("=== トークン設定の確認 ===")
    
    # 現在の設定を確認
    current_tokens = os.getenv("MAX_COMPLETION_TOKENS", "2000")
    print(f"現在の設定: MAX_COMPLETION_TOKENS = {current_tokens}")
    
    # 推奨設定
    print("\n推奨設定:")
    print("- 短い回答（要約）: 1000-2000")
    print("- 標準的な回答: 2000-4000")
    print("- 詳細な回答: 4000-8000")
    print("- 最大値: 12800")
    
    # 現在の設定の評価
    try:
        token_value = int(current_tokens)
        if token_value < 1000:
            print(f"\n⚠️ 現在の設定（{token_value}）は低すぎる可能性があります")
            print("   より長い回答が必要な場合は値を増やしてください")
        elif token_value > 8000:
            print(f"\n⚠️ 現在の設定（{token_value}）は高すぎる可能性があります")
            print("   処理時間が長くなる可能性があります")
        else:
            print(f"\n✅ 現在の設定（{token_value}）は適切です")
    except ValueError:
        print(f"\n❌ 無効な設定値: {current_tokens}")
    
    # .envファイルの確認
    env_path = Path(".env")
    if env_path.exists():
        print(f"\n.envファイルが存在します: {env_path}")
        
        # MAX_COMPLETION_TOKENSの行を確認
        with open(env_path, encoding='utf-8') as f:
            lines = f.readlines()
            max_tokens_line = None
            for i, line in enumerate(lines):
                if line.startswith("MAX_COMPLETION_TOKENS"):
                    max_tokens_line = (i, line.strip())
                    break
            
            if max_tokens_line:
                print(f"設定行 {max_tokens_line[0]+1}: {max_tokens_line[1]}")
            else:
                print("MAX_COMPLETION_TOKENSの設定が見つかりません")
                print("追加することをお勧めします")
    else:
        print(f"\n.envファイルが存在しません: {env_path}")
    
    # 設定の提案
    print("\n=== 設定の提案 ===")
    print("1. 短い回答のみ必要な場合:")
    print("   MAX_COMPLETION_TOKENS=1000")
    print("\n2. 標準的な使用（推奨）:")
    print("   MAX_COMPLETION_TOKENS=2000")
    print("\n3. 詳細な分析が必要な場合:")
    print("   MAX_COMPLETION_TOKENS=4000")
    print("\n4. 最大限の詳細が必要な場合:")
    print("   MAX_COMPLETION_TOKENS=8000")
    
    print("\n=== 使用方法 ===")
    print("1. .envファイルに以下を追加:")
    print("   MAX_COMPLETION_TOKENS=2000")
    print("\n2. アプリケーションを再起動")
    print("\n3. 必要に応じて値を調整")

if __name__ == "__main__":
    configure_tokens()
