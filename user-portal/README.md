# User Portal

Standalone registration and login service for the Arena Helper user portal.

## Run locally

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
uvicorn main:app --reload
```

The default database is `user_portal.db` in this directory. Set `DATABASE_URL` for Postgres and `SECRET_KEY` for JWT signing before starting the service.

Endpoints:

- `POST /auth/register`
- `POST /auth/login`
- `GET /health`
