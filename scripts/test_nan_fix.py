#!/usr/bin/env python3
"""
NaN値処理のテストスクリプト
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


def test_nan_handling():
    """NaN値処理のテスト"""
    print("NaN値処理のテストを開始...")
    
    # テストデータ(NaN値を含む)
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
        }
    ]
    
    try:
        # スライド生成器の初期化
        generator = SlideGenerator()
        print("✓ スライド生成器の初期化完了")
        
        # 総コスト計算のテスト
        total_cost = generator.calculate_total_cost(products)
        print(f"✓ 総コスト計算完了: {total_cost}")
        
        # プレゼンテーション生成のテスト(API使用なし)
        print("プレゼンテーション生成中（API使用なし）...")
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
        output_path = project_root / "temp" / "test_nan_fix.pptx"
        output_path.parent.mkdir(exist_ok=True)
        
        with open(output_path, "wb") as f:
            f.write(pptx_data)
        
        print(f"✓ プレゼンテーションを保存: {output_path}")
        print("✓ NaN値処理のテストが完了しました！")
        
        return True
        
    except Exception as e:
        print(f"✗ エラーが発生: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_nan_handling()
    sys.exit(0 if success else 1)
