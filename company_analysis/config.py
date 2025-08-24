
import os
from dataclasses import dataclass
from dotenv import load_dotenv

# Load .env (override to ensure interactive changes win)
load_dotenv(".env", override=True)

API_VERSION = os.getenv("API_VERSION") or "2024-12-01-preview"

@dataclass
class Settings:
    use_azure: bool
    api_version: str
    azure_endpoint: str | None
    azure_api_key: str | None
    openai_api_key: str | None
    default_model: str
    default_embed_model: str
    azure_chat_deployment: str | None
    azure_embed_deployment: str | None
    # search
    bing_search_key: str | None
    tavily_api_key: str | None
    # misc
    debug: bool = False

def get_settings() -> Settings:
    # If AZURE_OPENAI_ENDPOINT is set, prefer Azure path
    azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    settings = Settings(
        use_azure = bool(azure_endpoint),
        api_version = os.getenv("API_VERSION", "2024-12-01-preview"),
        azure_endpoint = azure_endpoint,
        azure_api_key = os.getenv("AZURE_OPENAI_API_KEY"),
        openai_api_key = os.getenv("OPENAI_API_KEY"),
        default_model = os.getenv("DEFAULT_MODEL", "gpt-5-mini"),
        default_embed_model = os.getenv("DEFAULT_EMBED_MODEL", "text-embedding-3-large"),
        azure_chat_deployment = os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT"),
        azure_embed_deployment = os.getenv("AZURE_OPENAI_EMBED_DEPLOYMENT"),
        bing_search_key = os.getenv("BING_SEARCH_KEY"),
        tavily_api_key = os.getenv("TAVILY_API_KEY"),
        debug = os.getenv("DEBUG", "0") == "1",
    )
    if settings.use_azure and not settings.azure_api_key:
        raise RuntimeError("AZURE_OPENAI_ENDPOINT is set but AZURE_OPENAI_API_KEY is missing.")
    if not settings.use_azure and not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is missing (and no Azure endpoint set).")
    return settings
