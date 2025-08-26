#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
スライド生成モジュールの使用例
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

from apps.streamlit.lib.slide_generator import SlideGenerator

def main():
    """メイン処理"""
    print("=== AIプレゼンテーション生成の例 ===")
    
    # サンプルデータ
    company_name = "株式会社サンプル"
    meeting_notes = """
    当社は製造業を営んでおり、以下の課題を抱えています：
    1. 生産性の向上が必要
    2. 在庫管理の最適化
    3. 品質管理の強化
    4. コスト削減の実現
    
    これらの課題解決のため、ITソリューションの導入を検討しています。
    """
    
    products = [
        {
            "id": "prod-001",
            "name": "生産管理システム",
            "category": "ERP",
            "price": 1500000,
            "description": "製造プロセスの統合管理システム",
            "tags": "生産管理,統合管理,リアルタイム"
        },
        {
            "id": "prod-002",
            "name": "在庫最適化ツール",
            "category": "SCM",
            "price": 800000,
            "description": "AI駆動の在庫最適化ソリューション",
            "tags": "在庫管理,AI,最適化"
        },
        {
            "id": "prod-003",
            "name": "品質管理プラットフォーム",
            "category": "QMS",
            "price": 1200000,
            "description": "包括的な品質管理と監視システム",
            "tags": "品質管理,監視,分析"
        }
    ]
    
    try:
        # スライド生成器の初期化
        print("スライド生成器を初期化中...")
        generator = SlideGenerator()
        
        # 設定
        use_tavily = True   # TAVILY API使用
        use_gpt = True      # GPT API使用
        tavily_uses = 2     # 製品あたり2回のAPI呼び出し
        
        print(f"設定: TAVILY={use_tavily}, GPT={use_gpt}, 呼び出し回数={tavily_uses}")
        
        # プレゼンテーション生成
        print("\nプレゼンテーション生成中...")
        pptx_data = generator.create_presentation(
            company_name=company_name,
            meeting_notes=meeting_notes,
            products=products,
            use_tavily=use_tavily,
            use_gpt=use_gpt,
            tavily_uses=tavily_uses
        )
        
        print(f"✓ プレゼンテーション生成完了: {len(pptx_data)}バイト")
        
        # ファイルに保存
        output_path = project_root / "temp" / "sample_presentation.pptx"
        output_path.parent.mkdir(exist_ok=True)
        
        with open(output_path, "wb") as f:
            f.write(pptx_data)
        
        print(f"✓ プレゼンテーションを保存: {output_path}")
        
        # 総コストの表示
        total_cost = generator.calculate_total_cost(products)
        print(f"\n総投資額: ¥{total_cost:,}")
        
        print("\n=== 完了 ===")
        
    except Exception as e:
        print(f"エラーが発生: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
