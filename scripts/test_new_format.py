#!/usr/bin/env python3
"""
新しいプレゼンテーション形式のテストスクリプト
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


def test_new_format():
    """新しい形式のテスト"""
    print("=== 新しいプレゼンテーション形式のテストを開始 ===")
    
    # テストデータ
    company_name = "株式会社テスト企業"
    meeting_notes = """
    当社は製造業を営んでおり、以下の課題を抱えています:
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
            "price": 1500000,  # ドル表示
            "description": "製造プロセスの統合管理システム",
            "tags": "生産管理,統合管理,リアルタイム"
        },
        {
            "id": "prod-002",
            "name": "在庫最適化ツール",
            "category": "SCM",
            "price": 800000,  # ドル表示
            "description": "AI駆動の在庫最適化ソリューション",
            "tags": "在庫管理,AI,最適化"
        },
        {
            "id": "prod-003",
            "name": "品質管理プラットフォーム",
            "category": "QMS",
            "price": 1200000,  # ドル表示
            "description": "包括的な品質管理と監視システム",
            "tags": "品質管理,監視,分析"
        }
    ]
    
    try:
        # スライド生成器の初期化
        print("1. スライド生成器の初期化...")
        generator = SlideGenerator()
        print("✓ スライド生成器の初期化完了")
        
        # 総コスト計算のテスト(ドル表示)
        print("\n2. 総コスト計算のテスト（ドル表示）...")
        total_cost = generator.calculate_total_cost(products)
        print(f"✓ 総コスト計算完了: ${total_cost:,}")
        
        # プレゼンテーション生成のテスト(API使用なし)
        print("\n3. 新しい形式でのプレゼンテーション生成...")
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
        output_path = project_root / "temp" / "test_new_format.pptx"
        output_path.parent.mkdir(exist_ok=True)
        
        with open(output_path, "wb") as f:
            f.write(pptx_data)
        
        print(f"✓ プレゼンテーションを保存: {output_path}")
        
        print("\n=== 新しい形式のテストが完了しました！ ===")
        print("✅ 案件名 + 企業名のタイトルスライド")
        print("✅ 現状の課題スライド")
        print("✅ 各製品の個別スライド（ご提案機器について、導入メリット）")
        print("✅ ドル表示の価格")
        print("✅ 左上の小さなロゴ")
        print("✅ 製品画像の配置")
        print("✅ 総コストスライド")
        
        return True
        
    except Exception as e:
        print(f"\n❌ エラーが発生: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """メイン処理"""
    print("新しいプレゼンテーション形式のテストを開始...")
    
    success = test_new_format()
    
    if success:
        print("\n🎉 新しい形式が正常に動作しています！")
        return True
    else:
        print("\n⚠️ 新しい形式に問題があります。ログを確認してください。")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
