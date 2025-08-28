"""
AIエージェント - プレゼンテーション生成用
Azure OpenAI API と TAVILY API を使用してプレゼンテーション内容を生成
"""

import os
from typing import Any

try:
    from dotenv import load_dotenv
    # 環境変数の読み込み
    load_dotenv(".env", override=True)
except ImportError:
    # dotenvが利用できない場合は環境変数を直接読み込む
    pass

try:
    from openai import AzureOpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

try:
    from tavily import TavilyClient
    TAVILY_AVAILABLE = True
except ImportError:
    TAVILY_AVAILABLE = False


class AIAgent:
    """プレゼンテーション生成用AIエージェント"""
    
    def __init__(self):
        """AIエージェントの初期化"""
        self.azure_client = None
        self.tavily_client = None
        self._init_clients()
    
    def _init_clients(self):
        """APIクライアントの初期化"""
        # Azure OpenAI クライアント
        if OPENAI_AVAILABLE:
            azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
            azure_api_key = os.getenv("AZURE_OPENAI_API_KEY")
            if azure_endpoint and azure_api_key:
                self.azure_client = AzureOpenAI(
                    azure_endpoint=azure_endpoint,
                    api_key=azure_api_key,
                    api_version="2024-12-01-preview"
                )
        
        # TAVILY クライアント
        if TAVILY_AVAILABLE:
            tavily_api_key = os.getenv("TAVILY_API_KEY")
            if tavily_api_key:
                self.tavily_client = TavilyClient(api_key=tavily_api_key)
    
    def generate_presentation_variables(
        self,
        project_name: str,
        company_name: str,
        meeting_notes: str,
        chat_history: str,
        products: list[dict[str, Any]],
        proposal_issues: list[dict[str, Any]],
        use_tavily: bool = True,
        use_gpt: bool = True,
        tavily_uses: int = 1
    ) -> dict[str, str]:
        """
        プレゼンテーション用変数を生成
        
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
            生成された変数の辞書
        """
        variables = {}
        
        # 基本変数
        variables["{{PROJECT_NAME}}"] = project_name
        variables["{{COMPANY_NAME}}"] = company_name
        
        # アジェンダ生成
        variables["{{AGENDA_BULLETS}}"] = self._generate_agenda_bullets(
            company_name, meeting_notes, products, use_gpt
        )
        
        # チャット履歴サマリー
        variables["{{CHAT_HISTORY_SUMMARY}}"] = self._generate_chat_summary(
            chat_history, use_gpt
        )
        
        # 課題仮説
        variables["{{PROBLEM_HYPOTHESES}}"] = self._generate_problem_hypotheses(
            proposal_issues, use_gpt
        )
        
        # 提案サマリー
        variables["{{PROPOSAL_SUMMARY}}"] = self._generate_proposal_summary(
            company_name, products, meeting_notes, use_gpt
        )
        
        # 製品変数
        for i, product in enumerate(products, 1):
            product_vars = self._generate_product_variables(
                product, i, use_tavily, use_gpt, tavily_uses
            )
            variables.update(product_vars)
        
        # 期待効果
        variables["{{EXPECTED_IMPACTS}}"] = self._generate_expected_impacts(
            company_name, products, meeting_notes, use_gpt
        )
        
        # 総コスト
        variables["{{TOTAL_COSTS}}"] = self._calculate_total_costs(products)
        
        # スケジュール計画
        variables["{{SCHEDULE_PLAN}}"] = self._generate_schedule_plan(
            company_name, products, use_gpt
        )
        
        # 次のアクション
        variables["{{NEXT_ACTIONS}}"] = self._generate_next_actions(
            company_name, products, use_gpt
        )
        
        # None値のチェックとクリーンアップ
        cleaned_variables = {}
        for key, value in variables.items():
            if value is None or value.strip() == "":
                print(f"⚠️ 警告: 変数 {key} の値が空です。デフォルト値を設定します。")
                # デフォルト値を設定
                if "AGENDA" in key:
                    cleaned_variables[key] = "• 現状分析\n• 課題整理\n• 提案概要\n• 導入効果\n• 導入計画"
                elif "CHAT_HISTORY" in key:
                    cleaned_variables[key] = "• 商談の詳細な内容が記録されています\n• 重要なポイントが整理されています\n• 決定事項が明確化されています"
                elif "PROBLEM_HYPOTHESES" in key:
                    cleaned_variables[key] = "• 業務効率化の課題が特定されています\n• コスト削減の機会が認識されています\n• システム統合の必要性が明確です"
                elif "PROPOSAL_SUMMARY" in key:
                    cleaned_variables[key] = f"• {company_name}向けの包括的なソリューション提案です\n• 複数の製品を組み合わせた最適解を提供します\n• 段階的な導入でリスクを最小化します"
                elif "EXPECTED_IMPACTS" in key:
                    cleaned_variables[key] = f"• {company_name}の業務効率化が期待されます\n• 生産性向上による時間短縮が実現されます\n• システム統合による運用コスト削減が可能です"
                elif "SCHEDULE_PLAN" in key:
                    cleaned_variables[key] = f"• {company_name}向けの段階的導入計画を提案します\n• 第1フェーズ：PoC実施（2-3ヶ月）\n• 第2フェーズ：本格導入（3-6ヶ月）"
                elif "NEXT_ACTIONS" in key:
                    cleaned_variables[key] = "• 詳細な提案書の作成を行います\n• 次回ミーティングの調整を行います\n• 技術要件の詳細確認を実施します"
                else:
                    cleaned_variables[key] = "• 情報を準備中"
            else:
                cleaned_variables[key] = value
        
        return cleaned_variables
    
    def _generate_agenda_bullets(
        self, company_name: str, meeting_notes: str, 
        products: list[dict[str, Any]], use_gpt: bool
    ) -> str:
        """アジェンダの生成"""
        if not use_gpt or not self.azure_client:
            return "• 現状分析\n• 課題整理\n• 提案概要\n• 導入効果\n• 導入計画"
        
        try:
            prompt = f"""
以下の情報を基に、プレゼンテーションのアジェンダを3-5行の箇条書きで生成してください。
各項目は簡潔で具体的にしてください。

企業名: {company_name}
商談メモ: {meeting_notes[:500]}
提案製品数: {len(products)}件

出力形式:
• [項目1]
• [項目2]
• [項目3]
"""
            
            response = self.azure_client.chat.completions.create(
                model="gpt-5-mini",
                messages=[
                    {"role": "system", "content": "あなたはB2B提案の専門家です。簡潔で実用的なアジェンダを作成してください。"},
                    {"role": "user", "content": prompt}
                ],
                max_completion_tokens=5000
            )
            
            content = response.choices[0].message.content or ""
            # 箇条書きの形式を統一
            lines = [line.strip() for line in content.split('\n') if line.strip()]
            bullet_points = []
            for line in lines:
                if line.startswith('•') or line.startswith('-') or line.startswith('*'):
                    bullet_points.append(line)
                else:
                    bullet_points.append(f"• {line}")
            
            return '\n'.join(bullet_points[:5])  # 最大5行
            
        except Exception as e:
            print(f"アジェンダ生成エラー: {e}")
            return "• 現状分析\n• 課題整理\n• 提案概要\n• 導入効果\n• 導入計画"
    
    def _generate_chat_summary(self, chat_history: str, use_gpt: bool) -> str:
        """チャット履歴のサマリー生成（箇条書き形式）"""
        if not chat_history.strip():
            return "• 商談履歴はありません"
        
        if not use_gpt or not self.azure_client:
            # フォールバック: 箇条書き形式で要約
            lines = chat_history.split('\n')[:5]  # 最大5行
            bullet_points = []
            for line in lines:
                if line.strip():
                    bullet_points.append(f"• {line.strip()}")
            return '\n'.join(bullet_points)
        
        try:
            prompt = f"""
以下の商談履歴を3-5行の箇条書きで要約してください。
重要なポイントや決定事項を中心にまとめてください。

商談履歴:
{chat_history[:1000]}

箇条書き要約:
"""
            
            response = self.azure_client.chat.completions.create(
                model="gpt-5-mini",
                messages=[
                    {"role": "system", "content": "あなたは商談履歴の要約専門家です。3-5行の箇条書きで要点を押さえた要約を作成してください。"},
                    {"role": "user", "content": prompt}
                ],
                max_completion_tokens=5000
            )
            
            content = response.choices[0].message.content or ""
            # 箇条書きの形式を統一
            lines = [line.strip() for line in content.split('\n') if line.strip()]
            bullet_points = []
            for line in lines:
                if line.startswith('•') or line.startswith('-') or line.startswith('*'):
                    bullet_points.append(line)
                else:
                    bullet_points.append(f"• {line}")
            
            return '\n'.join(bullet_points[:5])  # 最大5行
            
        except Exception as e:
            print(f"チャット履歴要約エラー: {e}")
            # フォールバック: 箇条書き形式
            lines = chat_history.split('\n')[:5]
            bullet_points = []
            for line in lines:
                if line.strip():
                    bullet_points.append(f"• {line.strip()}")
            return '\n'.join(bullet_points)
    
    def _generate_problem_hypotheses(
        self, proposal_issues: list[dict[str, Any]], use_gpt: bool
    ) -> str:
        """課題仮説の生成（箇条書き形式）"""
        if not proposal_issues:
            return "• 具体的な課題は特定されていません"
        
        if not use_gpt or not self.azure_client:
            # フォールバック: 箇条書き形式で課題を列挙
            bullet_points = []
            for issue in proposal_issues[:5]:  # 最大5件
                bullet_points.append(f"• {issue.get('issue', '')} (重み: {issue.get('weight', 0):.2f})")
            return '\n'.join(bullet_points)
        
        try:
            issues_text = "\n".join([
                f"• {issue.get('issue', '')} (重み: {issue.get('weight', 0):.2f})"
                for issue in proposal_issues
            ])
            
            prompt = f"""
以下の課題情報を基に、企業が抱える潜在的な問題を3-5行の箇条書きで分析してください。
ビジネスインパクトの観点から整理してください。

課題リスト:
{issues_text}

箇条書き問題分析:
"""
            
            response = self.azure_client.chat.completions.create(
                model="gpt-5-mini",
                messages=[
                    {"role": "system", "content": "あなたはB2B課題分析の専門家です。3-5行の箇条書きで具体的で実用的な問題分析を行ってください。"},
                    {"role": "user", "content": prompt}
                ],
                max_completion_tokens=5000
            )
            
            content = response.choices[0].message.content or ""
            # 箇条書きの形式を統一
            lines = [line.strip() for line in content.split('\n') if line.strip()]
            bullet_points = []
            for line in lines:
                if line.startswith('•') or line.startswith('-') or line.startswith('*'):
                    bullet_points.append(line)
                else:
                    bullet_points.append(f"• {line}")
            
            return '\n'.join(bullet_points[:5])  # 最大5行
            
        except Exception as e:
            print(f"課題仮説生成エラー: {e}")
            # フォールバック: 箇条書き形式
            bullet_points = []
            for issue in proposal_issues[:5]:
                bullet_points.append(f"• {issue.get('issue', '')} (重み: {issue.get('weight', 0):.2f})")
            return '\n'.join(bullet_points)
    
    def _generate_proposal_summary(
        self, company_name: str, products: list[dict[str, Any]], 
        meeting_notes: str, use_gpt: bool
    ) -> str:
        """提案サマリーの生成（箇条書き形式）"""
        if not use_gpt or not self.azure_client:
            # フォールバック: 箇条書き形式で製品名を列挙
            bullet_points = [f"• {company_name}向けの包括的ソリューション提案"]
            for product in products[:4]:  # 最大4件
                bullet_points.append(f"• {product.get('name', '')} ({product.get('category', '')})")
            return '\n'.join(bullet_points)
        
        try:
            product_info = "\n".join([
                f"• {p.get('name', '')} ({p.get('category', '')})"
                for p in products
            ])
            
            prompt = f"""
以下の情報を基に、提案の概要を3-5行の箇条書きで作成してください。
企業の課題解決に焦点を当てた提案内容にしてください。

企業名: {company_name}
商談メモ: {meeting_notes[:300]}
提案製品:
{product_info}

箇条書き提案概要:
"""
            
            response = self.azure_client.chat.completions.create(
                model="gpt-5-mini",
                messages=[
                    {"role": "system", "content": "あなたはB2B提案の専門家です。3-5行の箇条書きで企業の課題解決に焦点を当てた提案概要を作成してください。"},
                    {"role": "user", "content": prompt}
                ],
                max_completion_tokens=5000
            )
            
            content = response.choices[0].message.content or ""
            # 箇条書きの形式を統一
            lines = [line.strip() for line in content.split('\n') if line.strip()]
            bullet_points = []
            for line in lines:
                if line.startswith('•') or line.startswith('-') or line.startswith('*'):
                    bullet_points.append(line)
                else:
                    bullet_points.append(f"• {line}")
            
            return '\n'.join(bullet_points[:5])  # 最大5行
            
        except Exception as e:
            print(f"提案サマリー生成エラー: {e}")
            # フォールバック: 箇条書き形式
            bullet_points = [f"• {company_name}向けの包括的ソリューション提案"]
            for product in products[:4]:
                bullet_points.append(f"• {product.get('name', '')} ({product.get('category', '')})")
            return '\n'.join(bullet_points)
    
    def _generate_product_variables(
        self, product: dict[str, Any], index: int, 
        use_tavily: bool, use_gpt: bool, tavily_uses: int
    ) -> dict[str, str]:
        """製品変数の生成"""
        variables = {}
        
        # 基本情報
        variables[f"{{{{PRODUCTS[{index}].NAME}}}}"] = product.get("name", "")
        variables[f"{{{{PRODUCTS[{index}].CATEGORY}}}}"] = product.get("category", "")
        
        # 価格
        price = product.get("price")
        if price is not None:
            try:
                price_float = float(price)
                variables[f"{{{{PRODUCTS[{index}].PRICE}}}}"] = f"${price_float:,.2f}"
            except (ValueError, TypeError):
                variables[f"{{{{PRODUCTS[{index}].PRICE}}}}"] = "$0.00"
        else:
            # 価格がない場合はLLMで推定
            variables[f"{{{{PRODUCTS[{index}].PRICE}}}}"] = self._estimate_product_price(
                product, use_gpt
            )
        
        # 選択理由
        variables[f"{{{{PRODUCTS[{index}].REASON}}}}"] = self._generate_product_reason(
            product, use_gpt
        )
        
        return variables
    
    def _estimate_product_price(self, product: dict[str, Any], use_gpt: bool) -> str:
        """製品価格の推定"""
        if not use_gpt or not self.azure_client:
            return "$1,000.00"  # デフォルト価格
        
        try:
            prompt = f"""
以下の製品の推定価格を米ドルで教えてください。
市場価格を考慮して現実的な価格を提示してください。

製品名: {product.get('name', '')}
カテゴリ: {product.get('category', '')}
説明: {product.get('description', '')[:200]}

推定価格（米ドル）:
"""
            
            response = self.azure_client.chat.completions.create(
                model="gpt-5-mini",
                messages=[
                    {"role": "system", "content": "あなたは製品価格推定の専門家です。現実的な市場価格を提示してください。"},
                    {"role": "user", "content": prompt}
                ],
                max_completion_tokens=5000
            )
            
            content = response.choices[0].message.content
            if content is None:
                return "$1,000.00"
            # 価格の抽出
            import re
            price_match = re.search(r'\$[\d,]+\.?\d*', content)
            if price_match:
                return price_match.group()
            else:
                return "$1,000.00"
                
        except Exception as e:
            print(f"価格推定エラー: {e}")
            return "$1,000.00"
    
    def _generate_product_reason(self, product: dict[str, Any], use_gpt: bool) -> str:
        """製品選択理由の生成"""
        if not use_gpt or not self.azure_client:
            return product.get("reason", "製品の特性と企業ニーズの適合性")
        
        try:
            prompt = f"""
以下の製品の選択理由を簡潔に説明してください。
企業の課題解決にどのように貢献するかを中心に説明してください。

製品名: {product.get('name', '')}
カテゴリ: {product.get('category', '')}
説明: {product.get('description', '')[:300]}

選択理由:
"""
            
            response = self.azure_client.chat.completions.create(
                model="gpt-5-mini",
                messages=[
                    {"role": "system", "content": "あなたはB2B製品提案の専門家です。企業の課題解決に焦点を当てた選択理由を作成してください。"},
                    {"role": "user", "content": prompt}
                ],
                max_completion_tokens=5000
            )
            
            content = response.choices[0].message.content
            if content is None:
                return "製品の特性と企業ニーズの適合性"
            return content[:200]
            
        except Exception as e:
            print(f"選択理由生成エラー: {e}")
            # フォールバック: 基本的な理由を返す
            return "製品の特性と企業ニーズの適合性"
    
    def _generate_expected_impacts(
        self, company_name: str, products: list[dict[str, Any]], 
        meeting_notes: str, use_gpt: bool
    ) -> str:
        """期待効果の生成（箇条書き形式）"""
        if not use_gpt or not self.azure_client:
            return f"• {company_name}の業務効率化とコスト削減が期待されます\n• 生産性向上による時間短縮\n• システム統合による運用コスト削減"
        
        try:
            product_names = [p.get("name", "") for p in products]
            
            prompt = f"""
以下の情報を基に、提案製品の導入による期待効果を3-5行の箇条書きで説明してください。
定量的・定性的な効果を含めてください。

企業名: {company_name}
商談メモ: {meeting_notes[:300]}
提案製品: {', '.join(product_names)}

箇条書き期待効果:
"""
            
            response = self.azure_client.chat.completions.create(
                model="gpt-5-mini",
                messages=[
                    {"role": "system", "content": "あなたはB2B導入効果分析の専門家です。3-5行の箇条書きで具体的で実現可能な効果を説明してください。"},
                    {"role": "user", "content": prompt}
                ],
                max_completion_tokens=5000
            )
            
            content = response.choices[0].message.content or ""
            # 箇条書きの形式を統一
            lines = [line.strip() for line in content.split('\n') if line.strip()]
            bullet_points = []
            for line in lines:
                if line.startswith('•') or line.startswith('-') or line.startswith('*'):
                    bullet_points.append(line)
                else:
                    bullet_points.append(f"• {line}")
            
            return '\n'.join(bullet_points[:5])  # 最大5行
            
        except Exception as e:
            print(f"期待効果生成エラー: {e}")
            return f"• {company_name}の業務効率化とコスト削減が期待されます\n• 生産性向上による時間短縮\n• システム統合による運用コスト削減"
    
    def _calculate_total_costs(self, products: list[dict[str, Any]]) -> str:
        """総コストの計算"""
        total = 0.0
        for product in products:
            price = product.get("price")
            if price is not None:
                try:
                    total += float(price)
                except (ValueError, TypeError):
                    continue
        
        if total > 0:
            return f"${total:,.2f}"
        else:
            return "$0.00"
    
    def _generate_schedule_plan(
        self, company_name: str, products: list[dict[str, Any]], use_gpt: bool
    ) -> str:
        """スケジュール計画の生成（箇条書き形式）"""
        if not use_gpt or not self.azure_client:
            return f"• {company_name}向けの段階的導入計画を提案します\n• 第1フェーズ：PoC実施（2-3ヶ月）\n• 第2フェーズ：本格導入（3-6ヶ月）"
        
        try:
            prompt = f"""
以下の情報を基に、製品導入のスケジュール計画を3-5行の箇条書きで作成してください。
現実的で実行可能な計画にしてください。

企業名: {company_name}
提案製品数: {len(products)}件

箇条書き導入スケジュール計画:
"""
            
            response = self.azure_client.chat.completions.create(
                model="gpt-5-mini",
                messages=[
                    {"role": "system", "content": "あなたはB2B導入計画の専門家です。3-5行の箇条書きで現実的で実行可能なスケジュールを作成してください。"},
                    {"role": "user", "content": prompt}
                ],
                max_completion_tokens=5000
            )
            
            content = response.choices[0].message.content or ""
            # 箇条書きの形式を統一
            lines = [line.strip() for line in content.split('\n') if line.strip()]
            bullet_points = []
            for line in lines:
                if line.startswith('•') or line.startswith('-') or line.startswith('*'):
                    bullet_points.append(line)
                else:
                    bullet_points.append(f"• {line}")
            
            return '\n'.join(bullet_points[:5])  # 最大5行
            
        except Exception as e:
            print(f"スケジュール計画生成エラー: {e}")
            return f"• {company_name}向けの段階的導入計画を提案します\n• 第1フェーズ：PoC実施（2-3ヶ月）\n• 第2フェーズ：本格導入（3-6ヶ月）"
    
    def _generate_next_actions(
        self, company_name: str, products: list[dict[str, Any]], use_gpt: bool
    ) -> str:
        """次のアクションの生成（箇条書き形式）"""
        if not use_gpt or not self.azure_client:
            return f"• {company_name}との詳細協議とPoC実施を提案します\n• 技術要件の詳細確認\n• 導入スケジュールの調整"
        
        try:
            prompt = f"""
以下の情報を基に、提案後の次のアクションを3-5行の箇条書きで作成してください。
具体的で実行可能なアクションにしてください。

企業名: {company_name}
提案製品数: {len(products)}件

箇条書き次のアクション:
"""
            
            response = self.azure_client.chat.completions.create(
                model="gpt-5-mini",
                messages=[
                    {"role": "system", "content": "あなたはB2B提案後のアクション計画の専門家です。3-5行の箇条書きで具体的で実行可能なアクションを提案してください。"},
                    {"role": "user", "content": prompt}
                ],
                max_completion_tokens=5000
            )
            
            content = response.choices[0].message.content or ""
            # 箇条書きの形式を統一
            lines = [line.strip() for line in content.split('\n') if line.strip()]
            bullet_points = []
            for line in lines:
                if line.startswith('•') or line.startswith('-') or line.startswith('*'):
                    bullet_points.append(line)
                else:
                    bullet_points.append(f"• {line}")
            
            return '\n'.join(bullet_points[:5])  # 最大5行
            
        except Exception as e:
            print(f"次のアクション生成エラー: {e}")
            return f"• {company_name}との詳細協議とPoC実施を提案します\n• 技術要件の詳細確認\n• 導入スケジュールの調整"
    
    def search_web_with_tavily(self, query: str, max_results: int = 3) -> str:
        """TAVILY APIを使用したWeb検索"""
        if not self.tavily_client:
            return "あいうえお"  # デフォルトテキスト
        
        try:
            response = self.tavily_client.search(
                query=query,
                search_depth="basic",
                max_results=max_results
            )
            
            if response.get("results"):
                results = []
                for result in response["results"][:max_results]:
                    title = result.get("title", "")
                    content = result.get("content", "")
                    if title and content:
                        results.append(f"{title}: {content[:100]}...")
                
                return "\n".join(results)
            else:
                return "あいうえお"
                
        except Exception as e:
            print(f"TAVILY検索エラー: {e}")
            return "あいうえお"
