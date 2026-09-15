from fastapi import FastAPI

from .db import Base, engine
from .telemetry import router as telemetry_router

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Arena Helper API")
app.include_router(telemetry_router)
