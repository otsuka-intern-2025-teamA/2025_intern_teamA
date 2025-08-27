"""
Streamlit アプリケーション用ライブラリ
スライド生成システムのモジュール群
"""

# 遅延インポートでエラーを回避
__all__ = [
    "AIAgent",
    "TemplateProcessor", 
    "create_temp_template",
    "cleanup_temp_template",
    "NewSlideGenerator"
]

def _import_modules():
    """モジュールを遅延インポート"""
    try:
        from .ai_agent import AIAgent
        from .template_processor import TemplateProcessor, create_temp_template, cleanup_temp_template
        from .new_slide_generator import NewSlideGenerator
        return True
    except ImportError:
        return False

# モジュールの利用可能性をチェック
_has_modules = _import_modules()
