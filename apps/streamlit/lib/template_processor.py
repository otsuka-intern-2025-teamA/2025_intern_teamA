"""
テンプレート処理モジュール - PowerPointテンプレートの変数置換
元のテキストの色、サイズ、フォントを保持しながら変数を置換
"""

import os
import shutil
from pathlib import Path
from typing import Dict, Any, Optional
from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE
from pptx.dml.color import RGBColor


class TemplateProcessor:
    """PowerPointテンプレート処理クラス"""
    
    def __init__(self, template_path: str):
        """
        テンプレート処理クラスの初期化
        
        Args:
            template_path: テンプレートファイルのパス
        """
        self.template_path = Path(template_path)
        if not self.template_path.exists():
            raise FileNotFoundError(f"テンプレートファイルが見つかりません: {template_path}")
    
    def process_template(
        self, 
        variables: Dict[str, str], 
        output_path: str,
        preserve_formatting: bool = True
    ) -> str:
        """
        テンプレートを処理して変数を置換
        
        Args:
            variables: 置換する変数の辞書
            output_path: 出力ファイルのパス
            preserve_formatting: フォーマット保持フラグ
            
        Returns:
            出力ファイルのパス
        """
        # テンプレートをコピー
        output_path = Path(output_path)
        shutil.copy2(self.template_path, output_path)
        
        # プレゼンテーションを開く
        prs = Presentation(output_path)
        
        # 各スライドで変数を置換
        total_replacements = 0
        for slide in prs.slides:
            total_replacements += self._process_slide(
                slide, variables, preserve_formatting
            )
        
        # 保存
        prs.save(output_path)
        
        print(f"テンプレート処理完了: {total_replacements}件の置換を実行")
        return str(output_path)
    
    def _process_slide(self, slide, variables: Dict[str, str], preserve_formatting: bool) -> int:
        """スライド内の変数を処理"""
        replacements = 0
        
        # スライド内の各シェイプを処理
        for shape in slide.shapes:
            replacements += self._process_shape(
                shape, variables, preserve_formatting
            )
        
        return replacements
    
    def _process_shape(self, shape, variables: Dict[str, str], preserve_formatting: bool) -> int:
        """シェイプ内の変数を処理"""
        replacements = 0
        
        # グループシェイプの場合は再帰処理
        if shape.shape_type == MSO_SHAPE_TYPE.GROUP:
            for sub_shape in shape.shapes:
                replacements += self._process_shape(
                    sub_shape, variables, preserve_formatting
                )
            return replacements
        
        # テキストフレームの処理
        if hasattr(shape, "has_text_frame") and shape.has_text_frame:
            replacements += self._process_text_frame(
                shape.text_frame, variables, preserve_formatting
            )
        
        # テーブルの処理
        if hasattr(shape, "has_table") and shape.has_table:
            replacements += self._process_table(
                shape.table, variables, preserve_formatting
            )
        
        return replacements
    
    def _process_text_frame(self, text_frame, variables: Dict[str, str], preserve_formatting: bool) -> int:
        """テキストフレーム内の変数を処理"""
        if not text_frame or not text_frame.text:
            return 0
        
        replacements = 0
        original_text = text_frame.text
        
        # 各変数をチェック
        for placeholder, value in variables.items():
            # None値と空文字列のチェック
            if value is None or value.strip() == "":
                print(f"⚠️ 警告: 変数 {placeholder} の値が空です。スキップします。")
                continue
                
            if placeholder in original_text:
                # フォーマット保持の場合は特別な処理
                if preserve_formatting:
                    replacements += self._replace_with_formatting(
                        text_frame, placeholder, value
                    )
                else:
                    # 単純な置換
                    text_frame.text = original_text.replace(placeholder, value)
                    replacements += 1
                break  # 一度に一つの変数のみ処理
        
        return replacements
    
    def _replace_with_formatting(self, text_frame, placeholder: str, value: str) -> int:
        """
        フォーマットを保持しながら変数を置換
        元のテキストの色、サイズ、フォントを保持
        """
        if not text_frame.text or placeholder not in text_frame.text:
            return 0
        
        # None値と空文字列のチェック
        if value is None or value.strip() == "":
            print(f"⚠️ 警告: 変数 {placeholder} の値が空です。スキップします。")
            return 0
        
        # 元のフォーマット情報を保存
        original_formats = []
        for paragraph in text_frame.paragraphs:
            for run in paragraph.runs:
                if placeholder in run.text:
                    # フォーマット情報を保存
                    format_info = {
                        'font_name': run.font.name,
                        'font_size': run.font.size,
                        'font_bold': run.font.bold,
                        'font_italic': run.font.italic,
                        'font_color': run.font.color.rgb if (run.font.color and hasattr(run.font.color, 'rgb') and run.font.color.rgb) else None,
                        'text': run.text
                    }
                    original_formats.append(format_info)
        
        # テキストを置換
        text_frame.text = text_frame.text.replace(placeholder, value)
        
        # フォーマットを復元
        if original_formats:
            # 新しいテキストの長さに合わせてフォーマットを調整
            new_text = text_frame.text
            current_pos = 0
            
            for format_info in original_formats:
                # 置換されたテキストの位置を特定
                if format_info['text'] in new_text:
                    # 該当する部分にフォーマットを適用
                    for paragraph in text_frame.paragraphs:
                        for run in paragraph.runs:
                            if current_pos < len(new_text):
                                # フォーマットを適用
                                if format_info['font_name']:
                                    run.font.name = format_info['font_name']
                                if format_info['font_size']:
                                    run.font.size = format_info['font_size']
                                if format_info['font_bold'] is not None:
                                    run.font.bold = format_info['font_bold']
                                if format_info['font_italic'] is not None:
                                    run.font.italic = format_info['font_italic']
                                if format_info['font_color']:
                                    run.font.color.rgb = format_info['font_color']
                                current_pos += len(run.text)
        
        return 1
    
    def _process_table(self, table, variables: Dict[str, str], preserve_formatting: bool) -> int:
        """テーブル内の変数を処理"""
        replacements = 0
        
        for row in table.rows:
            for cell in row.cells:
                if cell.text_frame:
                    replacements += self._process_text_frame(
                        cell.text_frame, variables, preserve_formatting
                    )
        
        return replacements
    
    def get_template_info(self) -> Dict[str, Any]:
        """テンプレートの情報を取得"""
        try:
            prs = Presentation(self.template_path)
            
            info = {
                "file_path": str(self.template_path),
                "file_size": self.template_path.stat().st_size,
                "slide_count": len(prs.slides),
                "slides": []
            }
            
            # 各スライドの情報を収集
            for i, slide in enumerate(prs.slides):
                slide_info = {
                    "slide_number": i + 1,
                    "shapes_count": len(slide.shapes),
                    "text_placeholders": []
                }
                
                # テキストプレースホルダーを検索
                for shape in slide.shapes:
                    if hasattr(shape, "has_text_frame") and shape.has_text_frame:
                        if shape.text_frame.text:
                            # 変数プレースホルダーを検索
                            import re
                            placeholders = re.findall(r'\{\{[^}]+\}\}', shape.text_frame.text)
                            if placeholders:
                                slide_info["text_placeholders"].extend(placeholders)
                
                info["slides"].append(slide_info)
            
            return info
            
        except Exception as e:
            return {
                "error": str(e),
                "file_path": str(self.template_path)
            }
    
    def validate_variables(self, variables: Dict[str, str]) -> Dict[str, Any]:
        """変数の妥当性を検証"""
        validation_result = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "unused_variables": [],
            "missing_placeholders": []
        }
        
        try:
            prs = Presentation(self.template_path)
            
            # テンプレート内のプレースホルダーを収集
            template_placeholders = set()
            for slide in prs.slides:
                for shape in slide.shapes:
                    if hasattr(shape, "has_text_frame") and shape.has_text_frame:
                        if shape.text_frame.text:
                            import re
                            placeholders = re.findall(r'\{\{[^}]+\}\}', shape.text_frame.text)
                            template_placeholders.update(placeholders)
            
            # 提供された変数をチェック
            provided_variables = set(variables.keys())
            
            # 未使用の変数
            unused = provided_variables - template_placeholders
            if unused:
                validation_result["warnings"].append(f"未使用の変数: {list(unused)}")
                validation_result["unused_variables"] = list(unused)
            
            # 不足しているプレースホルダー
            missing = template_placeholders - provided_variables
            if missing:
                validation_result["errors"].append(f"不足している変数: {list(missing)}")
                validation_result["missing_placeholders"] = list(missing)
                validation_result["valid"] = False
            
            # 空の値のチェック
            empty_values = [k for k, v in variables.items() if not v or v.strip() == ""]
            if empty_values:
                validation_result["warnings"].append(f"空の値を持つ変数: {empty_values}")
            
        except Exception as e:
            validation_result["valid"] = False
            validation_result["errors"].append(f"テンプレート読み込みエラー: {str(e)}")
        
        return validation_result


def create_temp_template(template_path: str, output_dir: str = None) -> str:
    """
    テンプレートの一時コピーを作成
    
    Args:
        template_path: 元のテンプレートパス
        output_dir: 出力ディレクトリ（Noneの場合は一時ディレクトリ）
        
    Returns:
        一時テンプレートのパス
    """
    import tempfile
    
    if output_dir is None:
        output_dir = tempfile.mkdtemp()
    
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    template_path = Path(template_path)
    temp_template = output_dir / f"temp_{template_path.name}"
    
    shutil.copy2(template_path, temp_template)
    
    return str(temp_template)


def cleanup_temp_template(temp_path: str):
    """一時テンプレートを削除"""
    try:
        os.remove(temp_path)
        print(f"一時テンプレートを削除しました: {temp_path}")
    except Exception as e:
        print(f"一時テンプレート削除エラー: {e}")
