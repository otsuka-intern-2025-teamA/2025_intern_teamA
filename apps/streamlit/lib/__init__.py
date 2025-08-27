"""
Streamlit アプリケーション用ライブラリ
スライド生成システムのモジュール群
"""

# 遅延インポートでエラーを回避
__all__ = [
    "AIAgent",
    "NewSlideGenerator",
    "TemplateProcessor",
    "cleanup_temp_template",
    "create_temp_template"
]

def _import_modules():
    """モジュールを遅延インポート"""
    try:
        from .ai_agent import AIAgent
        from .new_slide_generator import NewSlideGenerator
        from .template_processor import TemplateProcessor, cleanup_temp_template, create_temp_template
        return True
    except ImportError:
        return False

# モジュールの利用可能性をチェック
_has_modules = _import_modules()
