from __future__ import annotations
import os
from dataclasses import dataclass
from dotenv import load_dotenv, find_dotenv

# .env をカレントに依存せず探索して読み込む
load_dotenv(find_dotenv(usecwd=True), override=True)

@dataclass
class SettingsRecommend:
    use_azure: bool
    api_version: str
    azure_endpoint: str | None
    azure_api_key: str | None
    openai_api_key: str | None
    default_model: str
    default_embed_model: str
    azure_chat_deployment: str | None
    azure_embed_deployment: str | None
    debug: bool = False

def get_settings_recommend() -> SettingsRecommend:
    # AZURE_OPENAI_ENDPOINT があれば Azure ルート、無ければ OpenAI ルート
    azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    use_azure = bool(azure_endpoint)

    s = SettingsRecommend(
        use_azure=use_azure,
        api_version=os.getenv("API_VERSION", "2024-12-01"),
        azure_endpoint=azure_endpoint,
        azure_api_key=os.getenv("AZURE_OPENAI_API_KEY"),
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        # OpenAI直の既定モデル（存在するものに修正）
        default_model=os.getenv("DEFAULT_MODEL", "gpt-5-mini"),
        default_embed_model=os.getenv("DEFAULT_EMBED_MODEL", "text-embedding-3-small"),
        # Azure は “デプロイ名” を渡す
        azure_chat_deployment=os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT"),
        azure_embed_deployment=os.getenv("AZURE_OPENAI_EMBED_DEPLOYMENT"),
        debug=os.getenv("DEBUG", "0") == "1",
    )

    # 必須チェック
    if s.use_azure and not s.azure_api_key:
        raise RuntimeError("AZURE_OPENAI_ENDPOINT は設定済みですが AZURE_OPENAI_API_KEY が未設定です。")
    if not s.use_azure and not s.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY が未設定です（Azure を使わない構成では必須）。")

    return s
