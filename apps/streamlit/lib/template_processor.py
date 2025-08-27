# template_processor.py
# ---------------------------------------------------------
# PPTXテンプレート処理モジュール
# - テンプレートPPTXのコピー作成
# - 変数の置換（フォーマット保持）
# - プレゼンテーションの生成
# ---------------------------------------------------------

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Dict, Any

from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE


class TemplateProcessor:
    """PPTXテンプレート処理クラス"""

    def __init__(self, template_path: Path):
        """初期化"""
        self.template_path = template_path
        if not template_path.exists():
            raise FileNotFoundError(f"テンプレートファイルが見つかりません: {template_path}")

    def create_presentation_from_template(
        self, 
        variables: Dict[str, str], 
        output_path: Path
    ) -> Path:
        """テンプレートからプレゼンテーションを生成"""
        
        print(f"📄 テンプレート処理開始: {self.template_path}")
        print(f"📤 出力先: {output_path}")
        print(f"🔧 変数数: {len(variables)}")
        
        # テンプレートをコピー
        shutil.copy2(self.template_path, output_path)
        print("✅ テンプレートコピー完了")
        
        # 変数を置換
        print("🔄 変数置換中...")
        self._replace_variables_in_pptx(output_path, variables)
        
        return output_path

    def _replace_variables_in_pptx(self, pptx_path: Path, variables: Dict[str, str]):
        """PPTXファイル内の変数を置換"""
        
        prs = Presentation(pptx_path)
        total_replacements = 0
        
        # 各スライドで変数を置換
        for slide in prs.slides:
            total_replacements += self._replace_variables_in_shapes(
                slide.shapes, variables
            )
        
        # 変更を保存
        prs.save(str(pptx_path))
        print(f"✅ 変数置換完了: {total_replacements}箇所")
        print(f"📁 ファイル保存完了: {pptx_path}")

    def _replace_variables_in_shapes(self, shapes, variables: Dict[str, str]) -> int:
        """シェイプ内の変数を置換（再帰的に処理）"""
        
        replacement_count = 0
        
        for shape in shapes:
            # グループ化されたシェイプを再帰処理
            if shape.shape_type == MSO_SHAPE_TYPE.GROUP:
                replacement_count += self._replace_variables_in_shapes(
                    shape.shapes, variables
                )
            
            # テキストフレーム内の変数を置換
            if hasattr(shape, "has_text_frame") and shape.has_text_frame:
                replacement_count += self._replace_variables_in_text_frame(
                    shape.text_frame, variables
                )
            
            # テーブル内の変数を置換
            if hasattr(shape, "has_table") and shape.has_table:
                replacement_count += self._replace_variables_in_table(
                    shape.table, variables
                )
        
        return replacement_count

    def _replace_variables_in_text_frame(self, text_frame, variables: Dict[str, str]) -> int:
        """テキストフレーム内の変数を置換（フォーマット保持）"""
        
        if not text_frame or not text_frame.text:
            return 0
        
        replacement_count = 0
        
        # 各変数を置換
        for placeholder, value in variables.items():
            # 値がNoneまたは空文字列の場合はスキップ
            if not value or str(value).strip() == "":
                continue
                
            if placeholder in text_frame.text:
                # 段落ごとに処理
                for paragraph in text_frame.paragraphs:
                    if placeholder in paragraph.text:
                        # 段落内の各ラン（テキストの一部）を処理
                        for run in paragraph.runs:
                            if placeholder in run.text:
                                # フォーマット情報を保存
                                original_font = run.font
                                font_info = {
                                    "name": original_font.name,
                                    "size": original_font.size,
                                    "bold": original_font.bold,
                                    "italic": original_font.italic,
                                    "underline": original_font.underline,
                                    "color": original_font.color.rgb if hasattr(original_font.color, 'rgb') and original_font.color.rgb else None,
                                }
                                
                                # テキストを置換
                                run.text = run.text.replace(placeholder, value)
                                
                                # フォーマットを復元
                                if font_info["name"]:
                                    run.font.name = font_info["name"]
                                if font_info["size"]:
                                    run.font.size = font_info["size"]
                                if font_info["bold"] is not None:
                                    run.font.bold = font_info["bold"]
                                if font_info["italic"] is not None:
                                    run.font.italic = font_info["italic"]
                                if font_info["underline"] is not None:
                                    run.font.underline = font_info["underline"]
                                if font_info["color"] and hasattr(run.font.color, 'rgb'):
                                    run.font.color.rgb = font_info["color"]
                                
                                replacement_count += 1
                                break  # この段落での置換は完了
        
        return replacement_count

    def _replace_variables_in_table(self, table, variables: Dict[str, str]) -> int:
        """テーブル内の変数を置換"""
        
        replacement_count = 0
        
        for row in table.rows:
            for cell in row.cells:
                replacement_count += self._replace_variables_in_text_frame(
                    cell.text_frame, variables
                )
        
        return replacement_count

    def _extract_format_info(self, text_frame) -> list:
        """テキストフレームのフォーマット情報を抽出"""
        
        format_info = []
        
        for paragraph in text_frame.paragraphs:
            para_info = {
                "alignment": paragraph.alignment,
                "runs": []
            }
            
            for run in paragraph.runs:
                run_info = {
                    "font_name": run.font.name,
                    "font_size": run.font.size,
                    "font_bold": run.font.bold,
                    "font_italic": run.font.italic,
                    "font_underline": run.font.underline,
                    "font_color": run.font.color.rgb if hasattr(run.font.color, 'rgb') and run.font.color.rgb else None,
                }
                para_info["runs"].append(run_info)
            
            format_info.append(para_info)
        
        return format_info

    def _restore_format_info(self, text_frame, format_info: list):
        """テキストフレームのフォーマット情報を復元"""
        
        for i, (para_info, paragraph) in enumerate(zip(format_info, text_frame.paragraphs)):
            if i < len(text_frame.paragraphs):
                # 段落のアライメントを復元
                paragraph.alignment = para_info["alignment"]
                
                # 各ラン（テキストの一部）のフォーマットを復元
                for j, run_info in enumerate(para_info["runs"]):
                    if j < len(paragraph.runs):
                        run = paragraph.runs[j]
                        
                        # フォント名
                        if run_info["font_name"]:
                            run.font.name = run_info["font_name"]
                        
                        # フォントサイズ
                        if run_info["font_size"]:
                            run.font.size = run_info["font_size"]
                        
                        # フォントスタイル
                        if run_info["font_bold"] is not None:
                            run.font.bold = run_info["font_bold"]
                        if run_info["font_italic"] is not None:
                            run.font.italic = run_info["font_italic"]
                        if run_info["font_underline"] is not None:
                            run.font.underline = run_info["font_underline"]
                        
                        # フォントカラー
                        if run_info["font_color"] and hasattr(run.font.color, 'rgb'):
                            run.font.color.rgb = run_info["font_color"]

    def get_template_info(self) -> Dict[str, Any]:
        """テンプレートの情報を取得"""
        
        prs = Presentation(self.template_path)
        
        info = {
            "slide_count": len(prs.slides),
            "slides": []
        }
        
        for i, slide in enumerate(prs.slides):
            slide_info = {
                "slide_number": i + 1,
                "title": slide.shapes.title.text if slide.shapes.title else "タイトルなし",
                "shapes_count": len(slide.shapes),
                "text_placeholders": []
            }
            
            # テキストプレースホルダーを検索
            for shape in slide.shapes:
                if hasattr(shape, "has_text_frame") and shape.has_text_frame:
                    if shape.text_frame.text:
                        slide_info["text_placeholders"].append(shape.text_frame.text[:100])
            
            info["slides"].append(slide_info)
        
        return info
