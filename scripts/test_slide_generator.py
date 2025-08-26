#!/usr/bin/env python3
"""
スライド生成機能のテストスクリプト
SlideGeneratorクラスの動作確認用
"""

import sys
from pathlib import Path

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from apps.streamlit.lib.slide_generator import SlideGenerator

def test_slide_generator():
    """スライド生成機能のテスト"""
    print("🧪 スライド生成機能のテストを開始します...")
    
    try:
        # SlideGeneratorインスタンスを作成
        generator = SlideGenerator()
        print("✅ SlideGeneratorの初期化が完了しました")
        
        # テストデータ
        company_name = "テスト株式会社"
        company_report = "テスト企業のレポートです。業務効率の改善が必要です。"
        user_input = "在庫管理の最適化を検討中です。"
        llm_proposal = """
提案の要旨（2〜3行）
テスト株式会社の業務効率を改善するため、高耐久キーボードとSSDを組み合わせたパッケージを提案します。

推奨商材（max 3 件）
- **Zowie CELERITAS**（カテゴリ：キーボード、概算価格：要見積／参考価格 ¥8,000〜¥15,000）
— 高耐久・高速入力が求められる営業・サポート部門の定番キーボード。

- **Zotac ZTSSD-A4P-120G**（カテゴリ：SSDストレージ、概算価格：要見積／参考価格 ¥3,000〜¥6,000）
— 古い端末や起動ディスク容量不足の改善用。

次のアクション（打ち手案）
- 小規模パイロット（5〜10台想定）を設定
- 正確な見積取得のためのベンダー確認
"""
        additional_instructions = "在庫最適化を中心に、需要予測と補充計画の連携を提案してください。"
        
        print("📊 プレゼンテーションを生成中...")
        
        # プレゼンテーションを生成（APIは使用しない）
        pptx_bytes = generator.generate_presentation(
            company_name=company_name,
            company_report=company_report,
            user_input=user_input,
            llm_proposal=llm_proposal,
            additional_instructions=additional_instructions,
            use_tavily_api=False,
            use_gpt_api=False,
            tavily_uses=3
        )
        
        print("✅ プレゼンテーションが正常に生成されました！")
        print(f"📁 ファイルサイズ: {len(pptx_bytes):,} バイト")
        
        # テストファイルとして保存（現在のプロジェクトフォルダ内）
        temp_dir = Path(__file__).parent.parent / "temp"
        temp_dir.mkdir(exist_ok=True)
        
        test_file_path = temp_dir / "test_presentation.pptx"
        with open(test_file_path, "wb") as f:
            f.write(pptx_bytes)
        
        print(f"💾 テストファイルが保存されました: {test_file_path.absolute()}")
        print(f"📁 保存場所: {temp_dir.absolute()}")
        
        return True
        
    except Exception as e:
        print(f"❌ エラーが発生しました: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_slide_generator()
    
    if success:
        print("\n🎉 テストが完了しました！")
    else:
        print("\n💥 テストが失敗しました。")
        sys.exit(1)
