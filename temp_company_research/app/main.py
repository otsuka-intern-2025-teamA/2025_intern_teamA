# app/main.py

# 1) できるだけ早く .env を読み込む
from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv(), override=False)

# 2) FastAPI とバリデーションのインポート
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, field_validator
from typing import List, Dict, Any


# 3) パイプラインのインポート
from research.pipeline import run_pipeline

# レポートで許可されているセクション
ALLOWED_SECTIONS = {"profile", "products", "market", "financials", "news"}

app = FastAPI(
    title="Company Research Backend (Tavily + Azure OpenAI gpt-5-mini)",
    version="0.1.0",
    description="POST /report -> Markdown + briefings + sources"
)

class ReportRequest(BaseModel):
    # レポート生成のための入力
    company_name: str = Field(..., min_length=1, description="会社名")
    # 会社名
    locale: str = Field(default="en", pattern="^(en|ja|ru)$", description="応答言語: en/ja/ru")
    # 応答言語: en/ja/ru
    sections: List[str] = Field(
        default_factory=list,
        description="レポートのセクション: profile, products, market, financials, news（デフォルトは全て）"
        # レポートのセクション: profile, products, market, financials, news（デフォルトは全て）
    )

    @field_validator("sections")
    @classmethod
    def validate_sections(cls, v: List[str]) -> List[str]:
        if not v:
            return v
        unknown = [s for s in v if s not in ALLOWED_SECTIONS]
        if unknown:
            raise ValueError(f"Unknown sections: {unknown}. Allowed: {sorted(ALLOWED_SECTIONS)}")
        return v

@app.get("/healthz")
async def health() -> Dict[str, str]:
    # ヘルスチェック用エンドポイント
    return {"status": "ok"}

@app.get("/")
async def root() -> Dict[str, Any]:
    # シンプルな挨拶とAPIの案内
    return {
        "name": "Company Research Backend",
        "endpoints": {
            "POST /report": {
                "body": {
                    "company_name": "Sony Group Corporation",
                    "locale": "ja",
                    "sections": ["profile", "products", "market", "financials", "news"]
                }
            },
            "GET /docs": "Swagger UI"
        }
    }

@app.post("/report")
async def create_report(req: ReportRequest) -> Dict[str, Any]:
    # メインメソッド：会社名を受け取り、以下を返す
    # - markdown: 完全なレポート
    # - briefings: セクションごとの内容（profile/products/market/financials/news）
    # - sources: ソース一覧（id/title/url）
    # - meta: メタ情報（resolved_name, source_count）
    try:
        sections = req.sections or ["profile", "products", "market", "financials", "news"]

        md, sources, meta, briefings = await run_pipeline(
            company=req.company_name,
            locale=req.locale,
            sections=sections
        )

        return {
            "company": req.company_name,
            "markdown": md,
            "sources": sources,
            "meta": meta,
            "briefings": briefings,
        }

    except Exception as e:
        # ここでロギングを追加可能（sentry/loguru など）
        raise HTTPException(status_code=500, detail=str(e))


# ローカル起動例："python -m app.main"（通常は uvicorn CLI で起動）
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
