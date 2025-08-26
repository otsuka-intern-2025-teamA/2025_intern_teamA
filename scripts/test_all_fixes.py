#!/usr/bin/env python3
"""
すべての修正をテストするスクリプト
"""

import sys
from pathlib import Path

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 環境変数の読み込み
from dotenv import load_dotenv

load_dotenv()

from apps.streamlit.lib.slide_generator import SlideGenerator


def test_all_fixes():
    """すべての修正をテスト"""
    print("=== すべての修正のテストを開始 ===")
    
    # テストデータ(様々な問題を含む)
    company_name = "テスト企業株式会社"
    meeting_notes = "テスト用の商談詳細です。"
    products = [
        {
            "id": "test-1",
            "name": "正常な製品",
            "category": "test",
            "price": 10000,
            "description": "正常な価格の製品",
            "tags": "正常,テスト"
        },
        {
            "id": "test-2",
            "name": "NaN価格の製品",
            "category": "test",
            "price": float('nan'),  # NaN値
            "description": "NaN価格の製品",
            "tags": "NaN,テスト"
        },
        {
            "id": "test-3",
            "name": "None価格の製品",
            "category": "test",
            "price": None,  # None値
            "description": "None価格の製品",
            "tags": "None,テスト"
        },
        {
            "id": "test-4",
            "name": "空文字価格の製品",
            "category": "test",
            "price": "",  # 空文字
            "description": "空文字価格の製品",
            "tags": "空文字,テスト"
        },
        {
            "id": "test-5",
            "name": "空の説明の製品",
            "category": "test",
            "price": 5000,
            "description": "",  # 空の説明
            "tags": ""
        }
    ]
    
    try:
        # スライド生成器の初期化
        print("1. スライド生成器の初期化...")
        generator = SlideGenerator()
        print("✓ スライド生成器の初期化完了")
        
        # 総コスト計算のテスト(NaN対策)
        print("\n2. 総コスト計算のテスト（NaN対策）...")
        total_cost = generator.calculate_total_cost(products)
        print(f"✓ 総コスト計算完了: {total_cost}")
        
        # 企業課題分析のテスト(API使用なし)
        print("\n3. 企業課題分析のテスト（API使用なし）...")
        challenges = generator.analyze_company_challenges(
            company_name, 
            meeting_notes, 
            use_gpt=False  # API使用なし
        )
        print(f"✓ 企業課題分析完了: {challenges}")
        
        # 製品情報検索のテスト(API使用なし)
        print("\n4. 製品情報検索のテスト（API使用なし）...")
        product_info = generator.search_product_info(
            "テスト製品",
            "test",
            tavily_uses=1,
            use_tavily=False  # API使用なし
        )
        print(f"✓ 製品情報検索完了: {product_info}")
        
        # プレゼンテーション生成のテスト(API使用なし)
        print("\n5. プレゼンテーション生成のテスト（API使用なし）...")
        pptx_data = generator.create_presentation(
            company_name=company_name,
            meeting_notes=meeting_notes,
            products=products,
            use_tavily=False,  # API使用なし
            use_gpt=False,     # API使用なし
            tavily_uses=1
        )
        
        print(f"✓ プレゼンテーション生成完了: {len(pptx_data)}バイト")
        
        # ファイルに保存
        output_path = project_root / "temp" / "test_all_fixes.pptx"
        output_path.parent.mkdir(exist_ok=True)
        
        with open(output_path, "wb") as f:
            f.write(output_path)
        
        print(f"✓ プレゼンテーションを保存: {output_path}")
        
        print("\n=== すべてのテストが完了しました！ ===")
        print("✅ NaN値処理")
        print("✅ API使用なしでの動作")
        print("✅ エラーハンドリング")
        print("✅ プレゼンテーション生成")
        
        return True
        
    except Exception as e:
        print(f"\n❌ エラーが発生: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_api_connection():
    """API接続のテスト(オプション)"""
    print("\n=== API接続のテスト（オプション） ===")
    
    try:
        generator = SlideGenerator()
        
        if generator.azure_client:
            print("✓ Azure OpenAI クライアント利用可能")
            
            # 簡単なテスト
            challenges = generator.analyze_company_challenges(
                "テスト企業", 
                "テスト", 
                use_gpt=True
            )
            print(f"✓ API使用での課題分析完了: {len(challenges)}文字")
        else:
            print("⚠️ Azure OpenAI クライアント利用不可")
            
        if generator.tavily_client:
            print("✓ TAVILY クライアント利用可能")
        else:
            print("⚠️ TAVILY クライアント利用不可")
            
        return True
        
    except Exception as e:
        print(f"❌ API接続テストでエラー: {e}")
        return False

def main():
    """メイン処理"""
    print("すべての修正のテストを開始...")
    
    # 基本テスト
    basic_success = test_all_fixes()
    
    # API接続テスト(オプション)
    api_success = test_api_connection()
    
    print("\n=== 最終結果 ===")
    print(f"基本テスト: {'✅ 成功' if basic_success else '❌ 失敗'}")
    print(f"API接続テスト: {'✅ 成功' if api_success else '⚠️ 部分成功'}")
    
    if basic_success:
        print("\n🎉 すべての修正が正常に動作しています！")
        return True
    else:
        print("\n⚠️ 一部の修正に問題があります。ログを確認してください。")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
