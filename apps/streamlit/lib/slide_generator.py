# slide_generator.py
# ---------------------------------------------------------
# AIエージェントによるプレゼンテーション生成モジュール
# - TAVILY API によるウェブ検索
# - Azure OpenAI GPT-5-mini によるLLM処理
# - python-pptx によるPPTX生成
# ---------------------------------------------------------

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from openai import AzureOpenAI
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.util import Inches, Pt
from tavily import TavilyClient

# プロジェクトルートとパス設定
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
LOGO_PATH = PROJECT_ROOT / "data" / "images" / "otsuka_logo.jpg"
PLACEHOLDER_IMG = PROJECT_ROOT / "data" / "images" / "example_picture.png"
TEMPLATE_PATH = PROJECT_ROOT / "data" / "templates" / "proposal_template.pptx"


class SlideGenerator:
    """AIエージェントによるプレゼンテーション生成クラス"""

    def __init__(self):
        """初期化:APIクライアントの準備"""
        self.azure_client = None
        self.tavily_client = None
        # トークン設定
        self.max_completion_tokens = int(os.getenv("MAX_COMPLETION_TOKENS", "2000"))

        # 画像パスの確認
        print(f"PROJECT_ROOT: {PROJECT_ROOT}")
        print(f"LOGO_PATH: {LOGO_PATH} (存在: {LOGO_PATH.exists()})")
        print(f"PLACEHOLDER_IMG: {PLACEHOLDER_IMG} (存在: {PLACEHOLDER_IMG.exists()})")

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

    def analyze_company_challenges(self, company_name: str, meeting_notes: str, use_gpt: bool = True) -> str:
        """企業の現状課題を分析"""
        if not use_gpt or not self.azure_client:
            return "あいうえお"

        try:
            prompt = f"""
以下の企業情報と商談詳細に基づいて、現状の課題を3-5点で分析してください。
各課題は具体的で、解決可能な内容にしてください。

企業名: {company_name}
商談詳細: {meeting_notes}

出力形式:
1. 課題1（具体的な説明）
2. 課題2（具体的な説明）
3. 課題3（具体的な説明）
...
"""

            response = self.azure_client.chat.completions.create(
                model="gpt-5-mini",
                messages=[
                    {
                        "role": "system",
                        "content": "あなたは企業分析の専門家です。具体的で実用的な課題分析を行ってください。",
                    },
                    {"role": "user", "content": prompt},
                ],
                max_completion_tokens=self.max_completion_tokens,
                # temperature=0.3 は GPT-5-mini でサポートされていないため削除
            )

            return response.choices[0].message.content.strip()
        except Exception as e:
            error_msg = str(e)
            if "max_tokens" in error_msg or "max_completion_tokens" in error_msg:
                print(f"課題分析でエラーが発生: トークン設定の問題 - {e}")
            elif "Could not finish the message because max_tokens" in error_msg:
                print(
                    "課題分析でエラーが発生: トークン制限に達しました。より高いmax_completion_tokensを設定してください。"
                )
            elif "400" in error_msg or "invalid_request_error" in error_msg:
                print(f"課題分析でエラーが発生: APIリクエストの問題 - {e}")
            else:
                print(f"課題分析でエラーが発生: {e}")
            return "あいうえお"

    def search_product_info(
        self, product_name: str, product_category: str, tavily_uses: int = 1, use_tavily: bool = True
    ) -> dict[str, str]:
        """製品情報のウェブ検索"""
        if not use_tavily or not self.tavily_client or tavily_uses <= 0:
            return {"description": "あいうえお", "benefits": "あいうえお", "features": "あいうえお"}

        try:
            # TAVILY API で製品情報を検索
            search_query = f"{product_name} {product_category} 製品仕様 特徴 導入メリット"

            response = self.tavily_client.search(
                query=search_query, search_depth="basic", max_results=min(tavily_uses, 5)
            )

            # 検索結果を要約
            if response.get("results"):
                content = " ".join([result.get("content", "") for result in response["results"][:tavily_uses]])

                # LLMで要約
                if self.azure_client:
                    summary_prompt = f"""
以下の検索結果から、製品の説明、特徴、導入メリットを抽出してください。

検索結果:
{content[:2000]}

出力形式（JSON）:
{{
  "description": "製品の説明（100字以内）",
  "features": "主な特徴（100字以内）",
  "benefits": "導入メリット（100字以内）"
}}
"""

                    summary_response = self.azure_client.chat.completions.create(
                        model="gpt-5-mini",
                        messages=[
                            {"role": "system", "content": "検索結果を簡潔に要約してください。"},
                            {"role": "user", "content": summary_prompt},
                        ],
                        response_format={"type": "json_object"},
                        max_completion_tokens=self.max_completion_tokens,
                        # temperature=0.2 は GPT-5-mini でサポートされていないため削除
                    )

                    try:
                        summary_data = json.loads(summary_response.choices[0].message.content)
                        return {
                            "description": summary_data.get("description", "あいうえお"),
                            "features": summary_data.get("features", "あいうえお"),
                            "benefits": summary_data.get("benefits", "あいうえお"),
                        }
                    except:
                        pass

                # フォールバック:検索結果を直接使用
                return {
                    "description": content[:200] + "..." if len(content) > 200 else content,
                    "features": "検索結果から抽出された特徴",
                    "benefits": "検索結果から抽出されたメリット",
                }

        except Exception as e:
            error_msg = str(e)
            if "max_tokens" in error_msg or "max_completion_tokens" in error_msg:
                print(f"製品情報検索でエラーが発生: トークン設定の問題 - {e}")
            elif "Could not finish the message because max_tokens" in error_msg:
                print(
                    "製品情報検索でエラーが発生: トークン制限に達しました。より高いmax_completion_tokensを設定してください。"
                )
            elif "400" in error_msg or "invalid_request_error" in error_msg:
                print(f"製品情報検索でエラーが発生: APIリクエストの問題 - {e}")
            else:
                print(f"製品情報検索でエラーが発生: {e}")

        return {"description": "あいうえお", "benefits": "あいうえお", "features": "あいうえお"}

    def calculate_total_cost(self, products: list[dict[str, Any]]) -> float:
        """総コストの計算(ドル表示、NaN対策)"""
        total = 0.0
        for product in products:
            price = product.get("price")
            if price and price is not None:
                try:
                    # NaNチェック
                    if str(price).lower() in ["nan", "none", ""]:
                        continue
                    price_float = float(price)
                    if price_float > 0 and not str(price_float).lower() == "nan":
                        total += price_float
                except (ValueError, TypeError):
                    continue
        return total

    def create_presentation(
        self,
        company_name: str,
        meeting_notes: str,
        products: list[dict[str, Any]],
        use_tavily: bool = True,
        use_gpt: bool = True,
        tavily_uses: int = 1,
    ) -> bytes:
        """プレゼンテーションPPTXの生成"""

        # データの検証
        if not company_name or not company_name.strip():
            company_name = "対象企業"

        if not meeting_notes or not meeting_notes.strip():
            meeting_notes = "商談詳細が入力されていません。"

        if not products:
            products = [
                {
                    "id": "no-product",
                    "name": "製品情報なし",
                    "category": "不明",
                    "price": None,
                    "description": "製品候補がありません",
                }
            ]

        # 新しいプレゼンテーションを作成
        prs = Presentation()

        # スライドサイズを16:9に設定
        prs.slide_width = Inches(13.33)
        prs.slide_height = Inches(7.5)

        # 1. タイトルスライド(案件名 + 企業名)
        self._create_title_slide(prs, company_name)

        # 2. 現状の課題スライド
        challenges = self.analyze_company_challenges(company_name, meeting_notes, use_gpt)
        self._create_challenges_slide(prs, company_name, challenges)

        # 3. 各製品の提案スライド(各製品を個別スライドに)
        for i, product in enumerate(products, 1):
            try:
                product_info = self.search_product_info(
                    product.get("name", ""), product.get("category", ""), tavily_uses, use_tavily
                )
                self._create_product_slide(prs, product, product_info, i)
            except Exception:
                # 製品スライド作成でエラーが発生した場合のフォールバック
                fallback_product = {
                    "id": product.get("id", f"error-{i}"),
                    "name": product.get("name", "製品情報エラー"),
                    "category": "不明",
                    "price": None,
                    "description": "製品情報の取得に失敗しました",
                }
                fallback_info = {
                    "description": "製品情報の取得に失敗しました",
                    "features": "詳細情報が利用できません",
                    "benefits": "要確認",
                }
                self._create_product_slide(prs, fallback_product, fallback_info, i)

        # 4. 総コストスライド
        total_cost = self.calculate_total_cost(products)
        self._create_cost_slide(prs, total_cost)

        # プレゼンテーションをバイトデータとして保存
        from io import BytesIO

        output = BytesIO()
        prs.save(output)
        output.seek(0)
        return output.getvalue()

    def _create_title_slide(self, prs: Presentation, company_name: str):
        """タイトルスライドの作成(案件名 + 企業名)"""
        slide_layout = prs.slide_layouts[6]  # 空白レイアウト
        slide = prs.slides.add_slide(slide_layout)

        # ロゴの追加(左上、小さなサイズ)
        print(f"ロゴ追加試行: {LOGO_PATH}")
        if LOGO_PATH.exists():
            try:
                slide.shapes.add_picture(str(LOGO_PATH), Inches(0.5), Inches(0.3), height=Inches(0.6))
                print("✓ ロゴの追加成功")
            except Exception as e:
                # ロゴの追加に失敗した場合のログ(デバッグ用)
                print(f"ロゴの追加に失敗: {e}")
                pass
        else:
            print(f"❌ ロゴファイルが存在しません: {LOGO_PATH}")

        # タイトル(案件名 + 企業名)
        title_box = slide.shapes.add_textbox(Inches(2), Inches(2), Inches(9), Inches(1.5))
        title_frame = title_box.text_frame
        title_frame.text = f"案件提案書\n{company_name}"

        title_para = title_frame.paragraphs[0]
        title_para.alignment = PP_ALIGN.CENTER
        if title_para.runs:  # runsが存在するかチェック
            title_run = title_para.runs[0]
            title_run.font.size = Pt(36)
            title_run.font.bold = True
            title_run.font.color.rgb = RGBColor(0, 0, 0)

        # 日付
        date_box = slide.shapes.add_textbox(Inches(2), Inches(4), Inches(9), Inches(0.5))
        date_frame = date_box.text_frame
        date_frame.text = f"作成日: {datetime.now().strftime('%Y年%m月%d日')}"

        date_para = date_frame.paragraphs[0]
        date_para.alignment = PP_ALIGN.CENTER
        if date_para.runs:  # runsが存在するかチェック
            date_run = date_para.runs[0]
            date_run.font.size = Pt(18)
            date_run.font.color.rgb = RGBColor(128, 128, 128)

    def _create_challenges_slide(self, prs: Presentation, company_name: str, challenges: str):
        """現状の課題スライドの作成"""
        slide_layout = prs.slide_layouts[6]
        slide = prs.slides.add_slide(slide_layout)

        # ロゴ(左上、小さなサイズ)
        print(f"ロゴ追加試行: {LOGO_PATH}")
        if LOGO_PATH.exists():
            try:
                slide.shapes.add_picture(str(LOGO_PATH), Inches(0.5), Inches(0.3), height=Inches(0.6))
                print("✓ ロゴの追加成功")
            except Exception as e:
                print(f"ロゴの追加に失敗: {e}")
                pass
        else:
            print(f"❌ ロゴファイルが存在しません: {LOGO_PATH}")

        # タイトル
        title_box = slide.shapes.add_textbox(Inches(1), Inches(1), Inches(11), Inches(1))
        title_frame = title_box.text_frame
        title_frame.text = "現状の課題"

        title_para = title_frame.paragraphs[0]
        title_para.alignment = PP_ALIGN.LEFT
        if title_para.runs:  # runsが存在するかチェック
            title_run = title_para.runs[0]
            title_run.font.size = Pt(28)
            title_run.font.bold = True

        # 課題内容
        content_box = slide.shapes.add_textbox(Inches(1), Inches(2.5), Inches(11), Inches(4))
        content_frame = content_box.text_frame
        content_frame.text = challenges

        content_para = content_frame.paragraphs[0]
        if content_para.runs:  # runsが存在するかチェック
            content_run = content_para.runs[0]
            content_run.font.size = Pt(16)
            content_run.font.color.rgb = RGBColor(0, 0, 0)

    def _create_product_slide(
        self, prs: Presentation, product: dict[str, Any], product_info: dict[str, str], product_num: int
    ):
        """製品提案スライドの作成(各製品を個別スライドに)"""
        slide_layout = prs.slide_layouts[6]
        slide = prs.slides.add_slide(slide_layout)

        # ロゴ(左上、小さなサイズ)
        if LOGO_PATH.exists():
            try:
                slide.shapes.add_picture(str(LOGO_PATH), Inches(0.5), Inches(0.3), height=Inches(0.6))
            except Exception as e:
                # ロゴの追加に失敗した場合のログ(デバッグ用)
                print(f"ロゴの追加に失敗: {e}")
                pass

        # タイトル
        title_box = slide.shapes.add_textbox(Inches(1), Inches(1), Inches(11), Inches(0.8))
        title_frame = title_box.text_frame
        title_frame.text = f"提案機{product_num}: {product.get('name', '')}"

        title_para = title_frame.paragraphs[0]
        title_para.alignment = PP_ALIGN.LEFT
        if title_para.runs:  # runsが存在するかチェック
            title_run = title_para.runs[0]
            title_run.font.size = Pt(24)
            title_run.font.bold = True

        # 製品画像(左側、適切なサイズ)
        print(f"製品画像追加試行: {PLACEHOLDER_IMG}")
        if PLACEHOLDER_IMG.exists():
            try:
                slide.shapes.add_picture(str(PLACEHOLDER_IMG), Inches(1), Inches(2), height=Inches(3))
                print("✓ 製品画像の追加成功")
            except Exception as e:
                # 画像の追加に失敗した場合のログ(デバッグ用)
                print(f"製品画像の追加に失敗: {e}")
                pass
        else:
            print(f"❌ 製品画像ファイルが存在しません: {PLACEHOLDER_IMG}")

        # 製品情報(右側)
        info_box = slide.shapes.add_textbox(Inches(6), Inches(2), Inches(6), Inches(4.5))
        info_frame = info_box.text_frame

        # ご提案機器について
        info_frame.text = f"ご提案機器について\n{product_info.get('description', '')}\n\n導入メリット\n{product_info.get('benefits', '')}"

        # 価格情報(ドル表示、NaN対策)
        price = product.get("price")
        if price and price is not None:
            try:
                # NaNチェック
                if str(price).lower() in ["nan", "none", ""]:
                    price_text = "\n\n価格: 要お見積もり"
                else:
                    price_float = float(price)
                    if price_float > 0:
                        price_text = f"\n\n価格: ${int(price_float):,}"
                    else:
                        price_text = "\n\n価格: 要お見積もり"
            except (ValueError, TypeError):
                price_text = "\n\n価格: 要お見積もり"
        else:
            price_text = "\n\n価格: 要お見積もり"

        info_frame.text += price_text

        # テキストのフォーマット
        for i, para in enumerate(info_frame.paragraphs):
            if para.runs:  # runsが存在するかチェック
                if i == 0:  # タイトル
                    para.runs[0].font.size = Pt(18)
                    para.runs[0].font.bold = True
                else:
                    para.runs[0].font.size = Pt(14)
                para.runs[0].font.color.rgb = RGBColor(0, 0, 0)

    def _create_cost_slide(self, prs: Presentation, total_cost: float):
        """総コストスライドの作成"""
        slide_layout = prs.slide_layouts[6]
        slide = prs.slides.add_slide(slide_layout)

        # ロゴ(左上、小さなサイズ)
        if LOGO_PATH.exists():
            try:
                slide.shapes.add_picture(str(LOGO_PATH), Inches(0.5), Inches(0.3), height=Inches(0.6))
            except Exception as e:
                # ロゴの追加に失敗した場合のログ(デバッグ用)
                print(f"ロゴの追加に失敗: {e}")
                pass

        # タイトル
        title_box = slide.shapes.add_textbox(Inches(1), Inches(1), Inches(11), Inches(1))
        title_frame = title_box.text_frame
        title_frame.text = "トータルコスト"

        title_para = title_frame.paragraphs[0]
        title_para.alignment = PP_ALIGN.CENTER
        title_run = title_para.runs[0]
        title_run.font.size = Pt(32)
        title_run.font.bold = True

        # コスト表示(NaN対策)
        cost_box = slide.shapes.add_textbox(Inches(2), Inches(3), Inches(9), Inches(2))
        cost_frame = cost_box.text_frame

        if total_cost > 0:
            cost_text = f"総投資額: ${int(total_cost):,}"
        else:
            cost_text = "総投資額: 要お見積もり"

        cost_frame.text = cost_text

        cost_para = cost_frame.paragraphs[0]
        cost_para.alignment = PP_ALIGN.CENTER
        if cost_para.runs:  # runsが存在するかチェック
            cost_run = cost_para.runs[0]
            cost_run.font.size = Pt(48)
            cost_run.font.bold = True
            cost_run.font.color.rgb = RGBColor(0, 100, 0)

        # 補足情報
        note_box = slide.shapes.add_textbox(Inches(2), Inches(5.5), Inches(9), Inches(1))
        note_frame = note_box.text_frame
        note_frame.text = "※ 価格は税抜き表示です\n※ 詳細な見積もりは別途お見積もりいたします"

        note_para = note_frame.paragraphs[0]
        if note_para.runs:  # runsが存在するかチェック
            note_run = note_para.runs[0]
            note_run.font.size = Pt(14)
            note_run.font.color.rgb = RGBColor(128, 128, 128)
