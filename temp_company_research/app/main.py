# app/main.py

from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv(), override=False)

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, field_validator
from typing import List, Dict, Any
import os

from research.pipeline import run_pipeline
from agent.runner import run_agentic  # ← NEW

ALLOWED_SECTIONS = {"profile", "products", "market", "financials", "news", "risks"}

DEFAULT_MODE = "agent" if os.getenv("AGENTIC_DEFAULT", "0") == "1" else "pipeline"

app = FastAPI(
    title="Company Research Backend (Agentic + Pipeline)",
    version="0.2.0",
    description="POST /report -> Markdown + briefings + sources"
)

class ReportRequest(BaseModel):
    company_name: str = Field(..., min_length=1)
    locale: str = Field(default="en", pattern="^(en|ja|ru)$")
    sections: List[str] = Field(default_factory=list)
    mode: str = Field(default=DEFAULT_MODE, pattern="^(agent|pipeline)$")

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
    return {"status": "ok"}

@app.post("/report")
async def create_report(req: ReportRequest) -> Dict[str, Any]:
    try:
        sections = req.sections or ["profile", "products", "market", "financials", "news", "risks"]

        if req.mode == "agent":
            md, sources, meta, briefings = await run_agentic(
                company=req.company_name, locale=req.locale, sections=sections,
                max_steps=int(os.getenv("MAX_AGENT_STEPS", "5"))
            )
        else:
            md, sources, meta, briefings = await run_pipeline(
                company=req.company_name, locale=req.locale, sections=sections
            )
            # старый пайплайн не возвращал briefings — но в нашей реализации возвращает

        return {
            "company": req.company_name,
            "markdown": md,
            "sources": sources,
            "meta": meta,
            "briefings": briefings,
            "mode": req.mode,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
