from fastapi import FastAPI

from auth import router as auth_router

app = FastAPI(title="Arena Helper User Portal")
app.include_router(auth_router, prefix="/auth")


@app.get("/health")
def health_check():
    return {"status": "ok"}
