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
        proposal_id: str = None,
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
        
        # 製品変数 - データベースから取得または渡されたリストを使用
        if proposal_id:
            # データベースから製品を取得
            db_products = self.get_products_from_db(proposal_id)
            if db_products:
                print(f"✅ データベースから{len(db_products)}件の製品を取得して変数を作成")
                for i, product in enumerate(db_products, 1):
                    product_vars = self._generate_product_variables(
                        product, i, use_tavily, use_gpt, tavily_uses
                    )
                    variables.update(product_vars)
                
                # 不足している製品変数を空文字で埋める（テンプレートの全プレースホルダーを置換するため）
                max_products_in_template = 9  # テンプレートには9行分の製品プレースホルダーがある
                for i in range(len(db_products) + 1, max_products_in_template + 1):
                    empty_product_vars = {
                        f"{{{{PRODUCTS[{i}].NAME}}}}": "",
                        f"{{{{PRODUCTS[{i}].CATEGORY}}}}": "",
                        f"{{{{PRODUCTS[{i}].PRICE}}}}": "",
                        f"{{{{PRODUCTS[{i}].REASON}}}}": "",
                        f"{{{{PRODUCTS[{i}].NOTE}}}}": ""
                    }
                    variables.update(empty_product_vars)
                
            else:
                print(f"⚠️ データベースから製品が取得できませんでした。渡されたリストを使用します。")
                # フォールバック: 渡されたリストを使用
                for i, product in enumerate(products, 1):
                    product_vars = self._generate_product_variables(
                        product, i, use_tavily, use_gpt, tavily_uses
                    )
                    variables.update(product_vars)
                
                # 不足している製品変数を空文字で埋める
                max_products_in_template = 9
                for i in range(len(products) + 1, max_products_in_template + 1):
                    empty_product_vars = {
                        f"{{{{PRODUCTS[{i}].NAME}}}}": "",
                        f"{{{{PRODUCTS[{i}].CATEGORY}}}}": "",
                        f"{{{{PRODUCTS[{i}].PRICE}}}}": "",
                        f"{{{{PRODUCTS[{i}].REASON}}}}": "",
                        f"{{{{PRODUCTS[{i}].NOTE}}}}": ""
                    }
                    variables.update(empty_product_vars)
        else:
            # proposal_idがない場合は渡されたリストを使用
            print(f"⚠️ proposal_idが指定されていません。渡されたリストを使用します。")
            for i, product in enumerate(products, 1):
                product_vars = self._generate_product_variables(
                    product, i, use_tavily, use_gpt, tavily_uses
                )
                variables.update(product_vars)
            
            # 不足している製品変数を空文字で埋める
            max_products_in_template = 9
            for i in range(len(products) + 1, max_products_in_template + 1):
                empty_product_vars = {
                    f"{{{{PRODUCTS[{i}].NAME}}}}": "",
                    f"{{{{PRODUCTS[{i}].CATEGORY}}}}": "",
                    f"{{{{PRODUCTS[{i}].PRICE}}}}": "",
                    f"{{{{PRODUCTS[{i}].REASON}}}}": "",
                    f"{{{{PRODUCTS[{i}].NOTE}}}}": ""
                }
                variables.update(empty_product_vars)
        
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
                    cleaned_variables[key] = ""
            else:
                cleaned_variables[key] = value
        
        # 最終的な変数の確認
        print(f"\n🎯 最終的に作成された変数一覧:")
        product_vars = {k: v for k, v in cleaned_variables.items() if "PRODUCTS" in k}
        if product_vars:
            print(f"📦 製品変数 ({len(product_vars)}件):")
            for key, value in product_vars.items():
                print(f"   {key}: {value}")
        else:
            print("⚠️ 製品変数が作成されていません！")
        
        print(f"📊 全変数数: {len(cleaned_variables)}件")
        
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
        name_key = f"{{{{PRODUCTS[{index}].NAME}}}}"
        category_key = f"{{{{PRODUCTS[{index}].CATEGORY}}}}"
        price_key = f"{{{{PRODUCTS[{index}].PRICE}}}}"
        reason_key = f"{{{{PRODUCTS[{index}].REASON}}}}"
        
        variables[name_key] = product.get("name", "")
        variables[category_key] = product.get("category", "")
        
        # 価格
        price = product.get("price")
        if price is not None and str(price).strip():
            try:
                price_float = float(price)
                variables[price_key] = f"${price_float:,.2f}"
            except (ValueError, TypeError):
                # 価格が無効な場合は推定
                variables[price_key] = self._estimate_product_price(
                    product, use_gpt, use_tavily
                )
        else:
            # 価格がない場合は推定（TAVILY API + LLM + フォールバック）
            variables[price_key] = self._estimate_product_price(
                product, use_gpt, use_tavily
            )
        
        # 選択理由
        variables[reason_key] = self._generate_product_reason(
            product, use_gpt
        )
        
        return variables
    
    def _estimate_product_price(self, product: dict[str, Any], use_gpt: bool, use_tavily: bool = True) -> str:
        """製品価格の推定（TAVILY API + LLM + フォールバック）"""
        # 1. まずTAVILY APIで価格を検索
        if use_tavily and self.tavily_client:
            tavily_price = self._estimate_product_price_with_tavily(product)
            if tavily_price:
                print(f"✅ TAVILY APIで価格を発見: {product.get('name', '')} = {tavily_price}")
                return tavily_price
        
        # 2. TAVILY APIで見つからない場合はLLMで推定
        if use_gpt and self.azure_client:
            try:
                prompt = f"""
以下の製品の推定価格を米ドルで教えてください。
市場価格を考慮して現実的な価格を提示してください。
価格のみを返してください（例：$1,500.00）。

製品名: {product.get('name', '')}
カテゴリ: {product.get('category', '')}
説明: {product.get('overview', '')[:200]}

推定価格（米ドル）:
"""
                
                response = self.azure_client.chat.completions.create(
                    model="gpt-5-mini",
                    messages=[
                        {"role": "system", "content": "あなたは製品価格推定の専門家です。価格のみを返してください（例：$1,500.00）。"},
                        {"role": "user", "content": prompt}
                    ],
                    max_completion_tokens=100
                )
                
                content = response.choices[0].message.content
                if content:
                    # 価格の抽出
                    import re
                    price_match = re.search(r'\$[\d,]+\.?\d*', content)
                    if price_match:
                        price_str = price_match.group()
                        print(f"✅ LLMで価格を推定: {product.get('name', '')} = {price_str}")
                        return price_str
                        
            except Exception as e:
                print(f"LLM価格推定エラー: {e}")
        
        # 3. フォールバック: カテゴリベースのデフォルト価格
        category = product.get('category', '').lower()
        default_prices = {
            'cpu': '$300.00',
            'memory': '$150.00',
            'storage': '$200.00',
            'network': '$500.00',
            'software': '$1,000.00',
            'hardware': '$800.00',
            'service': '$2,000.00',
            'case': '$150.00',
            'fan': '$50.00',
            'cooler': '$100.00',
            'hard-drive': '$200.00',
            'headphones': '$100.00',
            'keyboard': '$80.00',
            'monitor': '$300.00',
            'motherboard': '$200.00',
            'mouse': '$50.00',
            'power-supply': '$150.00',
            'video-card': '$400.00'
        }
        
        for cat_key, default_price in default_prices.items():
            if cat_key in category:
                print(f"⚠️ カテゴリベースのデフォルト価格を使用: {product.get('name', '')} = {default_price}")
                return default_price
        
        # 4. 最終フォールバック
        print(f"⚠️ 最終フォールバック価格を使用: {product.get('name', '')} = $1,000.00")
        return "$1,000.00"
    
    def _generate_product_reason(self, product: dict[str, Any], use_gpt: bool) -> str:
        """製品選択理由の生成"""
        # データベースに理由がある場合はそれを使用
        if product.get("reason") and str(product.get("reason")).strip():
            return str(product.get("reason")).strip()
        
        if not use_gpt or not self.azure_client:
            return "製品の特性と企業ニーズの適合性"
        
        try:
            prompt = f"""
以下の製品の選択理由を簡潔に説明してください。
企業の課題解決にどのように貢献するかを中心に説明してください。

製品名: {product.get('name', '')}
カテゴリ: {product.get('category', '')}
説明: {product.get('overview', '')[:300]}

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
        """総コストの計算（製品価格 + 導入コスト）"""
        total_products = 0.0
        implementation_cost = 0.0
        
        # 製品価格の合計を計算
        for product in products:
            price = product.get("price")
            if price is not None:
                try:
                    # 文字列から数値に変換（$記号やカンマを除去）
                    if isinstance(price, str):
                        price_clean = price.replace('$', '').replace(',', '').strip()
                        if price_clean:
                            price_num = float(price_clean)
                            total_products += price_num
                    else:
                        total_products += float(price)
                except (ValueError, TypeError):
                    continue
        
        # 導入コストの計算（製品数に基づく）
        if len(products) > 0:
            # 基本導入コスト
            base_implementation = 2000.0  # $2,000
            
            # 製品数に応じた追加コスト
            if len(products) <= 3:
                additional_cost = len(products) * 500.0  # 製品1つあたり$500
            elif len(products) <= 6:
                additional_cost = len(products) * 400.0  # 製品1つあたり$400
            else:
                additional_cost = len(products) * 300.0  # 製品1つあたり$300
            
            implementation_cost = base_implementation + additional_cost
        
        # 総コスト
        total_cost = total_products + implementation_cost
        
        if total_cost > 0:
            return f"${total_cost:,.2f}"
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
    
    def get_products_from_db(self, proposal_id: str) -> list[dict[str, Any]]:
        """データベースから提案製品を取得"""
        try:
            import sqlite3
            from pathlib import Path
            
            # データベースパスの設定
            project_root = Path(__file__).parent.parent.parent.parent
            db_path = project_root / "data" / "sqlite" / "app.db"
            
            if not db_path.exists():
                print(f"⚠️ データベースファイルが見つかりません: {db_path}")
                return []
            
            with sqlite3.connect(db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT rank, product_id, name, category, price, reason, overview, score, source_csv, image_url
                    FROM proposal_products
                    WHERE proposal_id = ?
                    ORDER BY rank
                """, (proposal_id,))
                
                rows = cursor.fetchall()
                products = []
                
                for row in rows:
                    product = {
                        "rank": row[0],
                        "product_id": row[1],
                        "name": row[2] or "",
                        "category": row[3] or "",
                        "price": row[4],
                        "reason": row[5] or "",
                        "overview": row[6] or "",
                        "score": row[7],
                        "source_csv": row[8] or "",
                        "image_url": row[9] or ""
                    }
                    products.append(product)
                    print(f"📋 製品データ: rank={product['rank']}, name='{product['name']}', category='{product['category']}', price='{product['price']}', reason='{product['reason']}'")
                
                print(f"✅ データベースから{len(products)}件の製品を取得: proposal_id={proposal_id}")
                return products
                
        except Exception as e:
            print(f"❌ データベースからの製品取得でエラーが発生: {e}")
            return []
    
    def _estimate_product_price_with_tavily(self, product: dict[str, Any]) -> str:
        """TAVILY APIを使用して製品価格を検索"""
        if not self.tavily_client:
            return None
        
        try:
            # 製品名とカテゴリで検索クエリを作成
            product_name = product.get('name', '').strip()
            category = product.get('category', '').strip()
            
            # より具体的な検索クエリを作成
            search_queries = [
                f'"{product_name}" price USD buy',
                f'"{product_name}" {category} price USD',
                f'{product_name} {category} cost price',
                f'{product_name} price dollars'
            ]
            
            for search_query in search_queries:
                print(f"🔍 TAVILY検索: {search_query}")
                
                response = self.tavily_client.search(
                    query=search_query,
                    search_depth="basic",
                    max_results=5
                )
                
                if response.get("results"):
                    # 検索結果から価格情報を抽出
                    for result in response["results"]:
                        content = result.get("content", "").lower()
                        title = result.get("title", "").lower()
                        url = result.get("url", "")
                        
                        # 価格パターンを検索（より詳細なパターン）
                        import re
                        price_patterns = [
                            r'\$[\d,]+\.?\d*',  # $1,000.00
                            r'[\d,]+\.?\d*\s*dollars?',  # 1,000.00 dollars
                            r'[\d,]+\.?\d*\s*usd',  # 1,000.00 USD
                            r'[\d,]+\.?\d*\s*\$',   # 1,000.00 $
                            r'[\d,]+\.?\d*\s*price',  # 1,000.00 price
                            r'price:\s*\$?[\d,]+\.?\d*',  # price: $1,000.00
                            r'cost:\s*\$?[\d,]+\.?\d*'    # cost: $1,000.00
                        ]
                        
                        for pattern in price_patterns:
                            matches = re.findall(pattern, content)
                            if matches:
                                # 価格の妥当性をチェック
                                for price_str in matches:
                                    # 数値部分を抽出
                                    num_match = re.search(r'[\d,]+\.?\d*', price_str)
                                    if num_match:
                                        try:
                                            price_num = float(num_match.group().replace(',', ''))
                                            # 妥当な価格範囲をチェック（$1 - $50,000）
                                            if 1 <= price_num <= 50000:
                                                formatted_price = f"${price_num:,.2f}"
                                                print(f"✅ TAVILYで価格発見: {product_name} = {formatted_price} (URL: {url})")
                                                return formatted_price
                                        except ValueError:
                                            continue
                
                # 次の検索クエリを試す前に少し待機
                import time
                time.sleep(0.5)
            
            print(f"⚠️ TAVILYで価格が見つかりませんでした: {product_name}")
            return None
            
        except Exception as e:
            print(f"TAVILY価格検索エラー: {e}")
            return None
