# new_slide_generator.py
# ---------------------------------------------------------
# 新しいスライド生成モジュール（テンプレートベース）
# - AIエージェントによる変数生成
# - テンプレートPPTXの処理
# - フォーマット保持による変数置換
# ---------------------------------------------------------

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

try:
    from .ai_agent import AIAgent
    from .template_processor import TemplateProcessor
except ImportError:
    # テスト用の絶対インポート
    from ai_agent import AIAgent
    from template_processor import TemplateProcessor


class NewSlideGenerator:
    """新しいスライド生成クラス（テンプレートベース）"""

    def __init__(self):
        """初期化"""
        # プロジェクトルートとパス設定
        self.project_root = Path(__file__).parent.parent.parent.parent
        self.template_path = self.project_root / "template" / "proposal_template.pptx"
        self.output_dir = self.project_root / "temp" / "generated_presentations"
        
        # 出力ディレクトリの作成
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # AIエージェントの初期化
        self.ai_agent = AIAgent()
        
        # テンプレートプロセッサの初期化
        if not self.template_path.exists():
            raise FileNotFoundError(f"テンプレートファイルが見つかりません: {self.template_path}")
        
        self.template_processor = TemplateProcessor(self.template_path)

    def create_presentation(
        self,
        project_name: str,
        company_name: str,
        meeting_notes: str,
        chat_history: str,
        products: List[Dict[str, Any]],
        use_gpt: bool = True,
        use_tavily: bool = True,
        tavily_uses: int = 2,
    ) -> bytes:
        """プレゼンテーションPPTXの生成（テンプレートベース）"""
        
        print(f"🎯 プレゼンテーション生成開始")
        print(f"企業名: {company_name}")
        print(f"製品数: {len(products)}")
        print(f"GPT API使用: {use_gpt}")
        print(f"TAVILY API使用: {use_tavily}")
        
        try:
            # 1. AIエージェントによる変数生成
            print("🤖 AIエージェントによる変数生成中...")
            variables = self.ai_agent.generate_presentation_variables(
                project_name=project_name,
                company_name=company_name,
                meeting_notes=meeting_notes,
                chat_history=chat_history,
                products=products,
                use_gpt=use_gpt,
                use_tavily=use_tavily,
                tavily_uses=tavily_uses,
            )
            
            print(f"✅ 変数生成完了: {len(variables)}個の変数")
            for key, value in variables.items():
                print(f"  {key}: {value[:50]}{'...' if len(value) > 50 else ''}")
            
            # 2. テンプレートからプレゼンテーション生成
            print("📄 テンプレート処理中...")
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_filename = f"{company_name}_提案書_{timestamp}.pptx"
            output_path = self.output_dir / output_filename
            
            self.template_processor.create_presentation_from_template(
                variables=variables,
                output_path=output_path
            )
            
            print(f"✅ プレゼンテーション生成完了: {output_path}")
            
            # 3. バイトデータとして返す
            with open(output_path, "rb") as f:
                pptx_data = f.read()
            
            # 4. 一時ファイルを削除
            output_path.unlink()
            
            return pptx_data
            
        except Exception as e:
            print(f"❌ プレゼンテーション生成でエラーが発生: {e}")
            raise

    def get_template_info(self) -> Dict[str, Any]:
        """テンプレートの情報を取得"""
        return self.template_processor.get_template_info()

    def preview_variables(
        self,
        project_name: str,
        company_name: str,
        meeting_notes: str,
        chat_history: str,
        products: List[Dict[str, Any]],
        use_gpt: bool = True,
        use_tavily: bool = True,
        tavily_uses: int = 2,
    ) -> Dict[str, str]:
        """変数のプレビュー（API呼び出しなし）"""
        
        print(f"🔍 変数プレビュー生成中...")
        print(f"  企業名: {company_name}")
        print(f"  製品数: {len(products)}")
        
        variables = {}
        
        # 基本変数
        print("  📝 基本変数設定中...")
        variables["{{PROJECT_NAME}}"] = project_name or "案件名未設定"
        variables["{{COMPANY_NAME}}"] = company_name or "企業名未設定"
        
        # 製品変数
        print(f"  📦 製品変数設定中... (製品数: {len(products)})")
        for i, product in enumerate(products):
            print(f"    📦 製品{i+1}: {product.get('name', '製品名未設定')}")
            prefix = f"{{{{PRODUCTS[{i}]."
            variables[f"{prefix}NAME}}"] = product.get("name", "製品名未設定")
            variables[f"{prefix}CATEGORY}}"] = product.get("category", "カテゴリ未設定")
            variables[f"{prefix}PRICE}}"] = self._format_price(product.get("price"))
            variables[f"{prefix}REASON}}"] = "あいうえお"  # デフォルト値
        
        # その他の変数
        print("  🔧 その他の変数設定中...")
        variables["{{CHAT_HISTORY_SUMMARY}}"] = "あいうえお"
        variables["{{PROBLEM_HYPOTHESES}}"] = "あいうえお"
        variables["{{PROPOSAL_SUMMARY}}"] = "あいうえお"
        variables["{{EXPECTED_IMPACTS}}"] = "あいうえお"
        variables["{{TOTAL_COSTS}}"] = "あいうえお"
        variables["{{SCHEDULE_PLAN}}"] = "あいうえお"
        variables["{{NEXT_ACTIONS}}"] = "あいうえお"
        variables["{{AGENDA_BULLETS}}"] = "あいうえお"
        
        print(f"  ✅ 変数プレビュー完了: {len(variables)}個の変数")
        return variables

    def _format_price(self, price) -> str:
        """価格のフォーマット"""
        if price is None or str(price).lower() in ["nan", "none", ""]:
            return "要お見積もり"
        
        try:
            price_float = float(price)
            if price_float > 0:
                return f"${int(price_float):,}"
            else:
                return "要お見積もり"
        except (ValueError, TypeError):
            return "要お見積もり"
