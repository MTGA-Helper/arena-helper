from fastapi import FastAPI
from fastapi.responses import FileResponse
from pathlib import Path

from auth import router as auth_router

app = FastAPI(title="Arena Helper User Portal")
app.include_router(auth_router, prefix="/auth")

LOGIN_PAGE = Path(__file__).with_name("login.html")
REGISTER_PAGE = Path(__file__).with_name("register.html")
USER_PAGE = Path(__file__).with_name("user.html")
DELETE_ACCOUNT_PAGE = Path(__file__).with_name("delete_account.html")


@app.get("/", include_in_schema=False)
@app.get("/login.html", include_in_schema=False)
def user_login_page():
    return FileResponse(LOGIN_PAGE)


@app.get("/register", include_in_schema=False)
@app.get("/register.html", include_in_schema=False)
def user_registration_page():
    return FileResponse(REGISTER_PAGE)


@app.get("/user.html", include_in_schema=False)
def user_profile_page():
    return FileResponse(USER_PAGE)


@app.get("/delete_account.html", include_in_schema=False)
def delete_account_page():
    return FileResponse(DELETE_ACCOUNT_PAGE)


@app.get("/health")
def health_check():
    return {"status": "ok"}
