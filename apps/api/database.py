import logging
import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy import create_engine
from dotenv import load_dotenv

load_dotenv()

# Fallback cleanly to SQLite if environment variables aren't set
DEFAULT_SQLITE_ASYNC = "sqlite+aiosqlite:///./arena.db"
DEFAULT_SQLITE_SYNC = "sqlite:///./arena.db"

logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL")
if DATABASE_URL is None:
    logger.warning("DATABASE_URL is not set; falling back to SQLite")
    DATABASE_URL = DEFAULT_SQLITE_ASYNC

SYNC_DATABASE_URL = os.getenv("SYNC_DATABASE_URL")
if SYNC_DATABASE_URL is None:
    logger.warning("SYNC_DATABASE_URL is not set; falling back to SQLite")
    SYNC_DATABASE_URL = DEFAULT_SQLITE_SYNC

# Async engine
if DATABASE_URL.startswith("sqlite"):
    engine = create_async_engine(
        DATABASE_URL,
        echo=False,
        future=True,
        connect_args={"check_same_thread": False},
    )
else:
    engine = create_async_engine(DATABASE_URL, echo=False, future=True)

AsyncSessionLocal = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# Synchronous engine
if SYNC_DATABASE_URL.startswith("sqlite"):
    sync_engine = create_engine(
        SYNC_DATABASE_URL,
        echo=False,
        future=True,
        connect_args={"check_same_thread": False},
    )
else:
    sync_engine = create_engine(SYNC_DATABASE_URL, echo=False, future=True)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=sync_engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
