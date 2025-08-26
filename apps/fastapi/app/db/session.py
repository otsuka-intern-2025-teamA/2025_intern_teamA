"""
データベース接続設定
SQLiteとSQLAlchemyの設定
"""
import os
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

# データベースファイルのパス設定
DB_PATH = os.getenv("DATABASE_URL", "data/sqlite/app.db")

# SQLiteのパスが相対パスの場合、プロジェクトルートからの絶対パスに変換
if not os.path.isabs(DB_PATH):
    project_root = Path(__file__).parent.parent.parent.parent.parent
    DB_PATH = str(project_root / DB_PATH)

# データベースディレクトリを作成
Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)

# SQLiteエンジンの作成
# SQLiteでFTS5とFOREIGN KEYSを有効化
DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(
    DATABASE_URL,
    connect_args={
        "check_same_thread": False,  # FastAPIでSQLiteを使用するため
        "timeout": 20,  # デッドロック回避
    },
    echo=False  # 開発時はTrueでSQLログを表示
)


# SQLiteでForeign Keyを有効化
@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.close()


# セッションファクトリの作成
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    """
    データベースセッションを取得するジェネレータ
    FastAPIの依存性注入で使用
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """
    データベースの初期化
    テーブル作成とスキーマ実行
    """
    from .models import Base
    
    # テーブル作成
    Base.metadata.create_all(bind=engine)
    
    # スキーマファイルがある場合は実行(FTS5等の設定)
    schema_path = Path(__file__).parent.parent.parent.parent.parent / "data" / "ddl" / "schema.sql"
    if schema_path.exists():
        with open(schema_path, encoding='utf-8') as f:
            schema_sql = f.read()
        
        # SQLiteに直接実行(SQLAlchemyでは実行できないFTS5等の設定)
        import sqlite3
        conn = sqlite3.connect(DB_PATH)
        try:
            conn.executescript(schema_sql)
            conn.commit()
        except Exception:
            pass
        finally:
            conn.close()