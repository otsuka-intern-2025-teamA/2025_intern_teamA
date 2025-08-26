#!/usr/bin/env python3
"""
スライド生成モジュールのテストスクリプト
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


def test_slide_generator():
    """スライド生成のテスト"""
    print("スライド生成モジュールのテストを開始...")
    
    # テストデータ
    company_name = "テスト企業株式会社"
    meeting_notes = "来期の需要予測精度向上と在庫最適化を目指しています。PoCから段階導入を検討中です。"
    products = [
        {
            "id": "test-1",
            "name": "高性能CPU",
            "category": "cpu",
            "price": 50000,
            "description": "最新の高性能CPU",
            "tags": "高性能,省電力"
        },
        {
            "id": "test-2", 
            "name": "大容量メモリ",
            "category": "memory",
            "price": 30000,
            "description": "大容量の高速メモリ",
            "tags": "大容量,高速"
        }
    ]
    
    try:
        # スライド生成器の初期化
        generator = SlideGenerator()
        print("✓ スライド生成器の初期化完了")
        
        # 企業課題分析のテスト
        challenges = generator.analyze_company_challenges(
            company_name, 
            meeting_notes, 
            use_gpt=True
        )
        print(f"✓ 企業課題分析完了: {len(challenges)}文字")
        
        # 製品情報検索のテスト
        product_info = generator.search_product_info(
            "高性能CPU",
            "cpu",
            tavily_uses=1,
            use_tavily=True
        )
        print(f"✓ 製品情報検索完了: {product_info}")
        
        # 総コスト計算のテスト
        total_cost = generator.calculate_total_cost(products)
        print(f"✓ 総コスト計算完了: ¥{total_cost:,}")
        
        # プレゼンテーション生成のテスト
        print("プレゼンテーション生成中...")
        pptx_data = generator.create_presentation(
            company_name=company_name,
            meeting_notes=meeting_notes,
            products=products,
            use_tavily=True,
            use_gpt=True,
            tavily_uses=1
        )
        
        print(f"✓ プレゼンテーション生成完了: {len(pptx_data)}バイト")
        
        # ファイルに保存
        output_path = project_root / "temp" / "test_presentation.pptx"
        output_path.parent.mkdir(exist_ok=True)
        
        with open(output_path, "wb") as f:
            f.write(pptx_data)
        
        print(f"✓ プレゼンテーションを保存: {output_path}")
        
    except Exception as e:
        print(f"✗ エラーが発生: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    print("すべてのテストが完了しました！")
    return True

if __name__ == "__main__":
    success = test_slide_generator()
    sys.exit(0 if success else 1)
