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

Email verification requires these environment variables:

```text
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USER=mailer@example.com
SMTP_PASSWORD=your-smtp-password
SMTP_FROM=mailer@example.com
USER_PORTAL_URL=http://localhost:8000
```

New accounts receive a verification link that expires after 24 hours. Login is blocked until the link is opened.

Endpoints:

- `POST /auth/register`
- `POST /auth/login`
- `GET /auth/verify-email?token=...`
- `GET /auth/me`
- `PATCH /auth/profile`
- `POST /auth/change-password`
- `GET /health`
