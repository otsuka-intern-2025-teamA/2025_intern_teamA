"""
新スライド生成システム - メインクラス
AIエージェントとテンプレート処理を統合してプレゼンテーションを生成
"""

import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

from .ai_agent import AIAgent
from .template_processor import TemplateProcessor, cleanup_temp_template, create_temp_template


class NewSlideGenerator:
    """新スライド生成システムのメインクラス"""
    def __init__(self, template_path=None):
        """
        スライド生成システムの初期化
        
        Args:
            template_path: テンプレートファイルのパス（Noneの場合はデフォルトパス探索）
        """
        # テンプレートパスの設定
        if template_path is None:
            project_root = Path(__file__).parent.parent.parent
            # ★ 探索順を強化：data/template → template → カレント相対
            candidates = [
                project_root / "data" / "template" / "proposal_template.pptx",
                project_root / "template" / "proposal_template.pptx",
                Path("data") / "template" / "proposal_template.pptx",
                Path("template") / "proposal_template.pptx",
            ]
            template_path = None
            print("🔍 テンプレート探索候補:")
            for p in candidates:
                print(f"  - {p} : exists={p.exists()}")
                if p.exists():
                    template_path = p
                    break
            if template_path is None:
                raise FileNotFoundError(
                    "テンプレートファイルが見つかりません。"
                    "data/template/proposal_template.pptx または template/ 配下に配置してください。"
                )

        self.template_path = Path(template_path)
        if not self.template_path.exists():
            raise FileNotFoundError(f"テンプレートファイルが見つかりません: {template_path}")
        
        # AIエージェントの初期化
        self.ai_agent = AIAgent()
        
        # テンプレート処理クラスの初期化
        self.template_processor = TemplateProcessor(str(self.template_path))
        
        print(f"✅ NewSlideGenerator初期化完了: {self.template_path}")
    
    def create_presentation(
        self,
        project_name: str,
        company_name: str,
        meeting_notes: str = "",
        chat_history: str = "",
        products: list[dict[str, Any]] = None,
        proposal_issues: list[dict[str, Any]] = None,
        use_tavily: bool = True,
        use_gpt: bool = True,
        tavily_uses: int = 1
    ) -> bytes:
        """
        プレゼンテーションを生成
        
        Args:
            project_name: プロジェクト名
            company_name: 企業名
            meeting_notes: 商談メモ
            chat_history: チャット履歴
            products: 製品リスト
            proposal_issues: 提案課題
            use_tavily: TAVILY API使用フラグ
            use_gpt: GPT API使用フラグ
            tavily_uses: 製品あたりのTAVILY API呼び出し回数
            
        Returns:
            生成されたプレゼンテーションのバイトデータ
        """
        print("🚀 プレゼンテーション生成開始")
        print(f"  プロジェクト名: {project_name}")
        print(f"  企業名: {company_name}")
        print(f"  製品数: {len(products) if products else 0}")
        print(f"  GPT API: {use_gpt}")
        print(f"  TAVILY API: {use_tavily}")
        print(f"  TAVILY使用回数: {tavily_uses}")
        
        try:
            # 1. AIエージェントで変数を生成
            print("🤖 AIエージェントで変数を生成中...")
            variables = self.ai_agent.generate_presentation_variables(
                project_name=project_name,
                company_name=company_name,
                meeting_notes=meeting_notes,
                chat_history=chat_history,
                products=products or [],
                proposal_issues=proposal_issues or [],
                use_tavily=use_tavily,
                use_gpt=use_gpt,
                tavily_uses=tavily_uses
            )
            
            print(f"✅ 変数生成完了: {len(variables)}件")
            
            # 2. 変数の妥当性を検証
            print("🔍 変数の妥当性を検証中...")
            validation = self.template_processor.validate_variables(variables)
            
            if not validation["valid"]:
                print(f"⚠️ 変数検証でエラーが発生: {validation['errors']}")
                if validation["missing_placeholders"]:
                    print(f"  不足しているプレースホルダー: {validation['missing_placeholders']}")
            
            if validation["warnings"]:
                print(f"⚠️ 警告: {validation['warnings']}")
            
            # 3. 一時テンプレートを作成
            print("📋 一時テンプレートを作成中...")
            temp_dir = tempfile.mkdtemp()
            temp_template_path = create_temp_template(str(self.template_path), temp_dir)
            
            # 4. テンプレートを処理
            print("⚙️ テンプレート処理中...")
            output_path = Path(temp_dir) / f"output_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pptx"
            
            processed_path = self.template_processor.process_template(
                variables=variables,
                output_path=str(output_path),
                preserve_formatting=True
            )
            
            # 5. 結果を読み込み
            print("📖 結果を読み込み中...")
            with open(processed_path, 'rb') as f:
                pptx_data = f.read()
            
            print(f"✅ プレゼンテーション生成完了: {len(pptx_data)} バイト")
            
            # 6. 一時ファイルをクリーンアップ
            try:
                cleanup_temp_template(temp_template_path)
                import shutil
                shutil.rmtree(temp_dir)
            except Exception as e:
                print(f"⚠️ 一時ファイルクリーンアップエラー: {e}")
            
            return pptx_data
            
        except Exception as e:
            print(f"❌ プレゼンテーション生成でエラーが発生: {e}")
            raise
    
    def get_template_info(self) -> dict[str, Any]:
        """テンプレートの詳細情報を取得"""
        return self.template_processor.get_template_info()
    
    def preview_variables(
        self,
        project_name: str,
        company_name: str,
        meeting_notes: str = "",
        chat_history: str = "",
        products: list[dict[str, Any]] = None,
        proposal_issues: list[dict[str, Any]] = None,
        use_tavily: bool = True,
        use_gpt: bool = True,
        tavily_uses: int = 1
    ) -> dict[str, Any]:
        """
        生成される変数のプレビューを表示
        
        Args:
            同様のパラメータ
            
        Returns:
            変数の辞書と検証結果
        """
        try:
            # 変数を生成
            variables = self.ai_agent.generate_presentation_variables(
                project_name=project_name,
                company_name=company_name,
                meeting_notes=meeting_notes,
                chat_history=chat_history,
                products=products or [],
                proposal_issues=proposal_issues or [],
                use_tavily=use_tavily,
                use_gpt=use_gpt,
                tavily_uses=tavily_uses
            )
            
            # 検証
            validation = self.template_processor.validate_variables(variables)
            
            return {
                "variables": variables,
                "validation": validation,
                "template_info": self.get_template_info()
            }
            
        except Exception as e:
            return {
                "error": str(e),
                "variables": {},
                "validation": {"valid": False, "errors": [str(e)]},
                "template_info": {}
            }
    
    def generate_with_custom_variables(
        self,
        custom_variables: dict[str, str],
        preserve_formatting: bool = True
    ) -> bytes:
        """
        カスタム変数を使用してプレゼンテーションを生成
        
        Args:
            custom_variables: カスタム変数の辞書
            preserve_formatting: フォーマット保持フラグ
            
        Returns:
            生成されたプレゼンテーションのバイトデータ
        """
        try:
            # 変数の妥当性を検証
            validation = self.template_processor.validate_variables(custom_variables)
            
            if not validation["valid"]:
                print(f"⚠️ 変数検証でエラーが発生: {validation['errors']}")
            
            # 一時テンプレートを作成
            temp_dir = tempfile.mkdtemp()
            temp_template_path = create_temp_template(str(self.template_path), temp_dir)
            
            # テンプレートを処理
            output_path = Path(temp_dir) / f"custom_output_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pptx"
            
            processed_path = self.template_processor.process_template(
                variables=custom_variables,
                output_path=str(output_path),
                preserve_formatting=preserve_formatting
            )
            
            # 結果を読み込み
            with open(processed_path, 'rb') as f:
                pptx_data = f.read()
            
            # 一時ファイルをクリーンアップ
            try:
                cleanup_temp_template(temp_template_path)
                import shutil
                shutil.rmtree(temp_dir)
            except Exception as e:
                print(f"⚠️ 一時ファイルクリーンアップエラー: {e}")
            
            return pptx_data
            
        except Exception as e:
            print(f"❌ カスタム変数でのプレゼンテーション生成でエラーが発生: {e}")
            raise
    
    def get_supported_variables(self) -> list[str]:
        """サポートされている変数のリストを取得"""
        template_info = self.get_template_info()
        if "error" in template_info:
            return []
        
        variables = set()
        for slide in template_info.get("slides", []):
            variables.update(slide.get("text_placeholders", []))
        
        return sorted(list(variables))
    
    def test_template_processing(self) -> dict[str, Any]:
        """テンプレート処理のテスト実行"""
        try:
            # テスト用の変数
            test_variables = {
                "{{PROJECT_NAME}}": "テストプロジェクト",
                "{{COMPANY_NAME}}": "テスト企業",
                "{{AGENDA_BULLETS}}": "• テスト項目1\n• テスト項目2",
                "{{CHAT_HISTORY_SUMMARY}}": "テスト用のチャット履歴サマリー",
                "{{PROBLEM_HYPOTHESES}}": "テスト用の課題仮説",
                "{{PROPOSAL_SUMMARY}}": "テスト用の提案サマリー",
                "{{EXPECTED_IMPACTS}}": "テスト用の期待効果",
                "{{TOTAL_COSTS}}": "$1,000.00",
                "{{SCHEDULE_PLAN}}": "テスト用のスケジュール計画",
                "{{NEXT_ACTIONS}}": "テスト用の次のアクション"
            }
            
            # 検証
            validation = self.template_processor.validate_variables(test_variables)
            
            return {
                "success": True,
                "validation": validation,
                "template_info": self.get_template_info(),
                "supported_variables": self.get_supported_variables()
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "template_info": {},
                "supported_variables": []
            }
