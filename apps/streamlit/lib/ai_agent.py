# ai_agent.py
# ---------------------------------------------------------
# AIエージェントによるプレゼンテーション変数生成モジュール
# - Azure OpenAI GPT-5-mini によるLLM処理
# - TAVILY API によるウェブ検索
# - プレゼンテーション変数の自動生成
# ---------------------------------------------------------

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from openai import AzureOpenAI
from tavily import TavilyClient


class AIAgent:
    """AIエージェントによるプレゼンテーション変数生成クラス"""

    def __init__(self):
        """初期化：APIクライアントの準備"""
        self.azure_client = None
        self.tavily_client = None
        # トークン設定
        self.max_completion_tokens = int(os.getenv("MAX_COMPLETION_TOKENS", "2000"))
        self._init_clients()

    def _init_clients(self):
        """Azure OpenAI と TAVILY API クライアントの初期化"""
        # Azure OpenAI クライアント
        try:
            api_version = os.getenv("API_VERSION", "2024-12-01-preview")
            self.azure_client = AzureOpenAI(
                azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
                api_key=os.getenv("AZURE_OPENAI_API_KEY"),
                api_version=api_version,
            )
            print(f"Azure OpenAI クライアント初期化完了: API version {api_version}")
        except Exception as e:
            print(f"Azure OpenAI クライアントの初期化に失敗: {e}")
            self.azure_client = None

        # TAVILY API クライアント
        try:
            api_key = os.getenv("TAVILY_API_KEY")
            if api_key:
                self.tavily_client = TavilyClient(api_key=api_key)
                print("TAVILY API クライアント初期化完了")
        except Exception as e:
            print(f"TAVILY API クライアントの初期化に失敗: {e}")
            self.tavily_client = None

    def generate_presentation_variables(
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
        """プレゼンテーション変数の生成"""
        
        variables = {}
        
        # 基本変数
        variables["{{PROJECT_NAME}}"] = project_name or "案件名未設定"
        variables["{{COMPANY_NAME}}"] = company_name or "企業名未設定"
        
        # チャット履歴サマリー
        chat_summary = self._generate_chat_summary(
            company_name, chat_history, use_gpt
        )
        print(f"    💬 チャット履歴サマリー結果: {chat_summary[:50] if chat_summary else 'None'}...")
        variables["{{CHAT_HISTORY_SUMMARY}}"] = chat_summary if chat_summary and chat_summary.strip() else "あいうえお"
        
        # 問題仮説
        print("🔍 問題仮説生成中...")
        problem_hypotheses = self._generate_problem_hypotheses(
            company_name, meeting_notes, chat_history, use_gpt
        )
        print(f"    🔍 問題仮説結果: {problem_hypotheses[:50] if problem_hypotheses else 'None'}...")
        variables["{{PROBLEM_HYPOTHESES}}"] = problem_hypotheses if problem_hypotheses and problem_hypotheses.strip() else "あいうえお"
        
        # 提案サマリー
        print("📋 提案サマリー生成中...")
        proposal_summary = self._generate_proposal_summary(
            company_name, products, meeting_notes, use_gpt
        )
        print(f"    📋 提案サマリー結果: {proposal_summary[:50] if proposal_summary else 'None'}...")
        variables["{{PROPOSAL_SUMMARY}}"] = proposal_summary if proposal_summary and proposal_summary.strip() else "あいうえお"
        
        # 製品変数
        print(f"📦 製品変数生成中... (製品数: {len(products)})")
        for i, product in enumerate(products):
            print(f"  📦 製品{i+1}: {product.get('name', '製品名未設定')}")
            prefix = f"{{{{PRODUCTS[{i}]."
            variables[f"{prefix}NAME}}"] = product.get("name", "製品名未設定")
            variables[f"{prefix}CATEGORY}}"] = product.get("category", "カテゴリ未設定")
            variables[f"{prefix}PRICE}}"] = self._format_price(product.get("price"))
            print(f"    💡 製品選択理由生成中...")
            product_reason = self._generate_product_reason(
                product, company_name, meeting_notes, use_tavily, tavily_uses, use_gpt
            )
            print(f"      💡 製品選択理由結果: {product_reason[:50] if product_reason else 'None'}...")
            variables[f"{prefix}REASON}}"] = product_reason if product_reason and product_reason.strip() else "あいうえお"
        
        # 期待される効果
        print("🎯 期待される効果生成中...")
        expected_impacts = self._generate_expected_impacts(
            products, company_name, use_gpt
        )
        print(f"    🎯 期待される効果結果: {expected_impacts[:50] if expected_impacts else 'None'}...")
        variables["{{EXPECTED_IMPACTS}}"] = expected_impacts if expected_impacts and expected_impacts.strip() else "あいうえお"
        
        # 総コスト
        print("💰 総コスト計算中...")
        total_cost = sum(
            float(p.get("price", 0)) for p in products 
            if p.get("price") and str(p.get("price")).lower() not in ["nan", "none", ""]
        )
        variables["{{TOTAL_COSTS}}"] = f"${int(total_cost):,}" if total_cost > 0 else "要お見積もり"
        print(f"  💰 総コスト: {variables['{{TOTAL_COSTS}}']}")
        
        # スケジュール計画
        print("📅 スケジュール計画生成中...")
        schedule_plan = self._generate_schedule_plan(
            products, company_name, use_gpt
        )
        print(f"    📅 スケジュール計画結果: {schedule_plan[:50] if schedule_plan else 'None'}...")
        variables["{{SCHEDULE_PLAN}}"] = schedule_plan if schedule_plan and schedule_plan.strip() else "あいうえお"
        
        # 次のアクション
        print("➡️ 次のアクション生成中...")
        next_actions = self._generate_next_actions(
            company_name, products, use_gpt
        )
        print(f"    ➡️ 次のアクション結果: {next_actions[:50] if next_actions else 'None'}...")
        variables["{{NEXT_ACTIONS}}"] = next_actions if next_actions and next_actions.strip() else "あいうえお"
        
        # アジェンダ（最後に生成）
        print("📋 アジェンダ生成中...")
        agenda_bullets = self._generate_agenda_bullets(variables, use_gpt)
        print(f"    📋 アジェンダ結果: {agenda_bullets[:50] if agenda_bullets else 'None'}...")
        variables["{{AGENDA_BULLETS}}"] = agenda_bullets if agenda_bullets and agenda_bullets.strip() else "あいうえお"
        
        print(f"✅ 変数生成完了: {len(variables)}個の変数")
        
        # 最終チェック: すべての変数がNoneでないことを確認
        print("🔍 最終チェック: 変数の内容確認")
        for key, value in variables.items():
            if value is None:
                print(f"  ❌ {key}: None (修正します)")
                variables[key] = "あいうえお"
            elif not str(value).strip():
                print(f"  ⚠️ {key}: 空文字列 (修正します)")
                variables[key] = "あいうえお"
            else:
                print(f"  ✅ {key}: OK")
        
        return variables

    def _generate_chat_summary(self, company_name: str, chat_history: str, use_gpt: bool) -> str:
        """チャット履歴のサマリー生成"""
        print(f"    💬 チャット履歴サマリー生成中... (GPT: {use_gpt})")
        if not use_gpt or not self.azure_client or not chat_history.strip():
            print("      ⚠️ GPT無効またはチャット履歴なし - デフォルト値を使用")
            return "あいうえお"
        
        try:
            prompt = f"""
以下の企業のチャット履歴を基に、企業の現状と課題を簡潔にまとめてください。

企業名: {company_name}
チャット履歴:
{chat_history}

出力形式: 100字以内で企業の現状と主要な課題をまとめてください。
"""
            
            response = self.azure_client.chat.completions.create(
                model="gpt-5-mini",
                messages=[
                    {"role": "system", "content": "あなたは企業分析の専門家です。簡潔で実用的なサマリーを作成してください。"},
                    {"role": "user", "content": prompt},
                ],
                max_completion_tokens=self.max_completion_tokens,
            )
            
            if response.choices and len(response.choices) > 0 and response.choices[0].message:
                content = response.choices[0].message.content.strip()
                return content if content else "あいうえお"
            else:
                print("チャット履歴サマリー生成でAPIレスポンスが不正です")
                return "あいうえお"
        except Exception as e:
            print(f"チャット履歴サマリー生成でエラーが発生: {e}")
            return "あいうえお"

    def _generate_problem_hypotheses(self, company_name: str, meeting_notes: str, chat_history: str, use_gpt: bool) -> str:
        """問題仮説の生成"""
        print(f"    🔍 問題仮説生成中... (GPT: {use_gpt})")
        if not use_gpt or not self.azure_client:
            print("      ⚠️ GPT無効 - デフォルト値を使用")
            return "あいうえお"
        
        try:
            prompt = f"""
以下の企業情報を基に、現状の課題を3-5点で分析してください。
各課題は具体的で、解決可能な内容にしてください。

企業名: {company_name}
商談詳細: {meeting_notes}
チャット履歴: {chat_history}

出力形式:
1. 課題1（具体的な説明）
2. 課題2（具体的な説明）
3. 課題3（具体的な説明）
...
"""
            
            response = self.azure_client.chat.completions.create(
                model="gpt-5-mini",
                messages=[
                    {"role": "system", "content": "あなたは企業分析の専門家です。具体的で実用的な課題分析を行ってください。"},
                    {"role": "user", "content": prompt},
                ],
                max_completion_tokens=self.max_completion_tokens,
            )
            
            if response.choices and len(response.choices) > 0 and response.choices[0].message:
                content = response.choices[0].message.content.strip()
                return content if content else "あいうえお"
            else:
                print("問題仮説生成でAPIレスポンスが不正です")
                return "あいうえお"
        except Exception as e:
            print(f"問題仮説生成でエラーが発生: {e}")
            return "あいうえお"

    def _generate_proposal_summary(self, company_name: str, products: List[Dict[str, Any]], meeting_notes: str, use_gpt: bool) -> str:
        """提案サマリーの生成"""
        print(f"    📋 提案サマリー生成中... (GPT: {use_gpt})")
        if not use_gpt or not self.azure_client:
            print("      ⚠️ GPT無効 - デフォルト値を使用")
            return "あいうえお"
        
        try:
            product_summary = "\n".join([
                f"- {p.get('name', '')} ({p.get('category', '')})"
                for p in products
            ])
            
            prompt = f"""
以下の企業への提案内容を基に、提案の全体像を簡潔にまとめてください。

企業名: {company_name}
商談詳細: {meeting_notes}
提案製品:
{product_summary}

出力形式: 150字以内で提案の全体像と期待される効果をまとめてください。
"""
            
            response = self.azure_client.chat.completions.create(
                model="gpt-5-mini",
                messages=[
                    {"role": "system", "content": "あなたは営業提案の専門家です。簡潔で魅力的な提案サマリーを作成してください。"},
                    {"role": "user", "content": prompt},
                ],
                max_completion_tokens=self.max_completion_tokens,
            )
            
            if response.choices and len(response.choices) > 0 and response.choices[0].message:
                content = response.choices[0].message.content.strip()
                return content if content else "あいうえお"
            else:
                print("提案サマリー生成でAPIレスポンスが不正です")
                return "あいうえお"
        except Exception as e:
            print(f"提案サマリー生成でエラーが発生: {e}")
            return "あいうえお"

    def _generate_product_reason(self, product: Dict[str, Any], company_name: str, meeting_notes: str, use_tavily: bool, tavily_uses: int, use_gpt: bool) -> str:
        """製品選択理由の生成"""
        print(f"      💡 製品選択理由生成中... (GPT: {use_gpt}, TAVILY: {use_tavily}, 使用回数: {tavily_uses})")
        if not use_gpt or not self.azure_client:
            print("        ⚠️ GPT無効 - デフォルト値を使用")
            return "あいうえお"
        
        try:
            # TAVILY APIで製品情報を検索
            product_info = ""
            if use_tavily and self.tavily_client and tavily_uses > 0:
                try:
                    search_query = f"{product.get('name', '')} {product.get('category', '')} 製品仕様 特徴 導入メリット"
                    response = self.tavily_client.search(
                        query=search_query,
                        search_depth="basic",
                        max_results=min(tavily_uses, 5)
                    )
                    
                    if response.get("results"):
                        content = " ".join([result.get("content", "") for result in response["results"][:tavily_uses]])
                        product_info = f"\n製品情報: {content[:300]}..."
                except Exception as e:
                    print(f"TAVILY API検索でエラーが発生: {e}")
            
            prompt = f"""
以下の製品を企業に提案する理由を生成してください。

企業名: {company_name}
商談詳細: {meeting_notes}
製品名: {product.get('name', '')}
製品カテゴリ: {product.get('category', '')}
製品価格: {self._format_price(product.get('price'))}
{product_info}

出力形式: 100字以内で、この製品を提案する具体的な理由を説明してください。
"""
            
            response = self.azure_client.chat.completions.create(
                model="gpt-5-mini",
                messages=[
                    {"role": "system", "content": "あなたは営業提案の専門家です。製品選択の理由を具体的に説明してください。"},
                    {"role": "user", "content": prompt},
                ],
                max_completion_tokens=self.max_completion_tokens,
            )
            
            if response.choices and len(response.choices) > 0 and response.choices[0].message:
                content = response.choices[0].message.content.strip()
                return content if content else "あいうえお"
            else:
                print("製品選択理由生成でAPIレスポンスが不正です")
                return "あいうえお"
        except Exception as e:
            print(f"製品選択理由生成でエラーが発生: {e}")
            return "あいうえお"

    def _generate_expected_impacts(self, products: List[Dict[str, Any]], company_name: str, use_gpt: bool) -> str:
        """期待される効果の生成"""
        print(f"    🎯 期待される効果生成中... (GPT: {use_gpt})")
        if not use_gpt or not self.azure_client:
            print("      ⚠️ GPT無効 - デフォルト値を使用")
            return "あいうえお"
        
        try:
            product_summary = "\n".join([
                f"- {p.get('name', '')} ({p.get('category', '')})"
                for p in products
            ])
            
            prompt = f"""
以下の製品導入により期待される効果を分析してください。

企業名: {company_name}
導入予定製品:
{product_summary}

出力形式: 150字以内で、製品導入により期待される具体的な効果と改善点を説明してください。
"""
            
            response = self.azure_client.chat.completions.create(
                model="gpt-5-mini",
                messages=[
                    {"role": "system", "content": "あなたはIT導入効果分析の専門家です。具体的で実現可能な効果を説明してください。"},
                    {"role": "user", "content": prompt},
                ],
                max_completion_tokens=self.max_completion_tokens,
            )
            
            if response.choices and len(response.choices) > 0 and response.choices[0].message:
                content = response.choices[0].message.content.strip()
                return content if content else "あいうえお"
            else:
                print("期待される効果生成でAPIレスポンスが不正です")
                return "あいうえお"
        except Exception as e:
            print(f"期待される効果生成でエラーが発生: {e}")
            return "あいうえお"

    def _generate_schedule_plan(self, products: List[Dict[str, Any]], company_name: str, use_gpt: bool) -> str:
        """スケジュール計画の生成"""
        print(f"    📅 スケジュール計画生成中... (GPT: {use_gpt})")
        if not use_gpt or not self.azure_client:
            print("      ⚠️ GPT無効 - デフォルト値を使用")
            return "あいうえお"
        
        try:
            product_summary = "\n".join([
                f"- {p.get('name', '')} ({p.get('category', '')})"
                for p in products
            ])
            
            prompt = f"""
以下の製品導入のスケジュール計画を作成してください。

企業名: {company_name}
導入予定製品:
{product_summary}

出力形式: 100字以内で、段階的な導入スケジュールを説明してください。
"""
            
            response = self.azure_client.chat.completions.create(
                model="gpt-5-mini",
                messages=[
                    {"role": "system", "content": "あなたはプロジェクト管理の専門家です。現実的で実行可能なスケジュールを作成してください。"},
                    {"role": "user", "content": prompt},
                ],
                max_completion_tokens=self.max_completion_tokens,
            )
            
            if response.choices and len(response.choices) > 0 and response.choices[0].message:
                content = response.choices[0].message.content.strip()
                return content if content else "あいうえお"
            else:
                print("スケジュール計画生成でAPIレスポンスが不正です")
                return "あいうえお"
        except Exception as e:
            print(f"スケジュール計画生成でエラーが発生: {e}")
            return "あいうえお"

    def _generate_next_actions(self, company_name: str, products: List[Dict[str, Any]], use_gpt: bool) -> str:
        """次のアクションの生成"""
        print(f"    ➡️ 次のアクション生成中... (GPT: {use_gpt})")
        if not use_gpt or not self.azure_client:
            print("      ⚠️ GPT無効 - デフォルト値を使用")
            return "あいうえお"
        
        try:
            product_summary = "\n".join([
                f"- {p.get('name', '')} ({p.get('category', '')})"
                for p in products
            ])
            
            prompt = f"""
以下の製品導入に向けた次のアクションを提案してください。

企業名: {company_name}
導入予定製品:
{product_summary}

出力形式: 100字以内で、具体的な次のステップとアクションを説明してください。
"""
            
            response = self.azure_client.chat.completions.create(
                model="gpt-5-mini",
                messages=[
                    {"role": "system", "content": "あなたは営業プロセスの専門家です。具体的で実行可能な次のアクションを提案してください。"},
                    {"role": "user", "content": prompt},
                ],
                max_completion_tokens=self.max_completion_tokens,
            )
            
            if response.choices and len(response.choices) > 0 and response.choices[0].message:
                content = response.choices[0].message.content.strip()
                return content if content else "あいうえお"
            else:
                print("次のアクション生成でAPIレスポンスが不正です")
                return "あいうえお"
        except Exception as e:
            print(f"次のアクション生成でエラーが発生: {e}")
            return "あいうえお"

    def _generate_agenda_bullets(self, variables: Dict[str, str], use_gpt: bool) -> str:
        """アジェンダの生成"""
        print(f"    📋 アジェンダ生成中... (GPT: {use_gpt})")
        if not use_gpt or not self.azure_client:
            print("      ⚠️ GPT無効 - デフォルト値を使用")
            return "あいうえお"
        
        try:
            # 既存の変数からアジェンダを生成
            content_summary = f"""
企業名: {variables.get('{{COMPANY_NAME}}', '')}
問題仮説: {variables.get('{{PROBLEM_HYPOTHESES}}', '')}
提案サマリー: {variables.get('{{PROPOSAL_SUMMARY}}', '')}
期待される効果: {variables.get('{{EXPECTED_IMPACTS}}', '')}
"""
            
            prompt = f"""
以下の内容を基に、プレゼンテーションのアジェンダ（目次）を作成してください。

{content_summary}

出力形式: 箇条書きで、論理的な流れに従ってアジェンダを作成してください。
"""
            
            response = self.azure_client.chat.completions.create(
                model="gpt-5-mini",
                messages=[
                    {"role": "system", "content": "あなたはプレゼンテーション構成の専門家です。論理的で魅力的なアジェンダを作成してください。"},
                    {"role": "user", "content": prompt},
                ],
                max_completion_tokens=self.max_completion_tokens,
            )
            
            if response.choices and len(response.choices) > 0 and response.choices[0].message:
                content = response.choices[0].message.content.strip()
                return content if content else "あいうえお"
            else:
                print("アジェンダ生成でAPIレスポンスが不正です")
                return "あいうえお"
        except Exception as e:
            print(f"アジェンダ生成でエラーが発生: {e}")
            return "あいうえお"

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
