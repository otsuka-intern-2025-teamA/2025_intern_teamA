"""
FastAPIアプリケーションのエントリーポイント
案件管理システムの中心的なAPIサーバー
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging

from .db.session import init_db
from .api.routers import cases, analysis, messages

# ログ設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """アプリケーション起動時・終了時の処理"""
    # 起動時
    logger.info("Initializing database...")
    try:
        init_db()
        logger.info("Database initialization completed")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        raise
    
    yield
    
    # 終了時
    logger.info("Shutting down...")

# FastAPIアプリケーション作成
app = FastAPI(
    title="案件管理システム API",
    description="企業分析機能付きの案件管理システム",
    version="1.0.0",
    lifespan=lifespan
)

# CORS設定（Streamlitフロントエンドからのアクセスを許可）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8501", "http://127.0.0.1:8501"],  # Streamlitデフォルトポート
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ルーターを登録
app.include_router(cases.router)
app.include_router(analysis.router)
app.include_router(messages.router)

@app.get("/")
async def root():
    """ヘルスチェック用エンドポイント"""
    return {
        "message": "案件管理システム API サーバーが稼働中",
        "status": "healthy",
        "version": "1.0.0"
    }

@app.get("/health")
async def health_check():
    """詳細なヘルスチェック"""
    from .db.session import SessionLocal
    from .db.models import Item
    
    try:
        # データベース接続確認
        db = SessionLocal()
        item_count = db.query(Item).count()
        db.close()
        
        return {
            "status": "healthy",
            "database": "connected",
            "items_count": item_count
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=503, detail="Service unavailable")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
        log_level="info"
    )