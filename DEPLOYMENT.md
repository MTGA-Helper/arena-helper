# Arena Helper Deployment Blueprint

## 1. Target Environment
- **Provider:** Hetzner, DigitalOcean, or Vultr
- **OS:** Ubuntu 24.04 (4GB RAM / 2 CPU recommended)
- **Containerization:** Docker & Docker Compose

## 2. Ports & Networking
- 8000: FastAPI Backend / Swagger Docs (/docs)
- 5432: PostgreSQL Database

## 3. Databases (Shared Production Server)
- rena_helper_dev (Used for development testing on dev branch)
- rena_helper_stable (Used for stable production on main branch)

## 4. Environment Variables (.env)
\\\env
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_secure_password
POSTGRES_DB=arena_helper_stable
GEMINI_API_KEY=your_gemini_api_key_here
\\\

## 5. Deployment Steps
1. SSH into the Ubuntu VPS.
2. Clone the repository (git clone https://github.com/owlensteed/arena-helper.git).
3. Create the .env file with production credentials.
4. Run docker compose up -d --build.
5. Verify API status at http://<server-ip>:8000/docs.
