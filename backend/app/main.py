from fastapi import FastAPI

from .db import Base, engine
from .analytics import router as analytics_router
from .telemetry import router as telemetry_router

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Arena Helper API")
app.include_router(telemetry_router)
app.include_router(analytics_router)
