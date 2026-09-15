from contextlib import asynccontextmanager
from fastapi import FastAPI
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
import structlog

logger = structlog.get_logger(__name__)

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str

settings = Settings()

engine = create_async_engine(settings.database_url, echo=True)
async_session_maker = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        async with async_session_maker() as session:
            await session.execute(text("SELECT 1"))
        logger.info("Database connection verified successfully.")
    except Exception as e:
        logger.error("Database connection failed", error=str(e))
    yield
    await engine.dispose()

app = FastAPI(title="Arena Helper API", lifespan=lifespan)

@app.get("/health")
async def health_check():
    return {"status": "ok", "database": "connected"}
