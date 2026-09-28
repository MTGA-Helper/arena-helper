# -*- coding: utf-8 -*-
from contextlib import asynccontextmanager
from fastapi import FastAPI
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
import structlog

# Import modular routers
from collection import router as collection_router
from matches import router as matches_router
from recommendations import router as recommendations_router
from router_match import router as router_match_router

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

# Register all modular routers
app.include_router(collection_router)
app.include_router(matches_router)
app.include_router(recommendations_router)
app.include_router(router_match_router)

@app.get("/health")
async def health_check():
    return {"status": "ok", "database": "connected"}