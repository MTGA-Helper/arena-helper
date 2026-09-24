param(
    [switch]$SkipSeeder
)

$ErrorActionPreference = "Stop"

Write-Host "==================================================" -ForegroundColor Cyan
Write-Host " Arena Helper API - Automation Pipeline" -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Cyan

if (-not $env:VIRTUAL_ENV) {
    if (Test-Path "venv\Scripts\Activate.ps1") {
        Write-Host "[+] Activating virtual environment..." -ForegroundColor Yellow
        . .\venv\Scripts\Activate.ps1
    } else {
        Write-Host "[-] Error: Virtual environment 'venv' not found in current directory." -ForegroundColor Red
        exit 1
    }
} else {
    Write-Host "[+] Virtual environment is already active." -ForegroundColor Green
}

Write-Host "[+] Checking / installing required packages..." -ForegroundColor Yellow
pip install PyJWT structlog pydantic-settings python-multipart httpx --quiet --disable-pip-version-check

if (-not (Test-Path ".env")) {
    Write-Host "[-] Error: .env configuration file missing!" -ForegroundColor Red
    exit 1
}
Write-Host "[+] Environment configuration file detected." -ForegroundColor Green

Write-Host "[+] Verifying database connection and schema tables..." -ForegroundColor Yellow
python -c "import asyncio; from database import engine, Base; from models import *; async def init(): 
    async with engine.begin() as conn: await conn.run_sync(Base.metadata.create_all)
asyncio.run(init())"
Write-Host "[+] Database tables verified successfully." -ForegroundColor Green

if (-not $SkipSeeder) {
    if (Test-Path "seed_cards.py") {
        Write-Host "[+] Executing idempotent Scryfall master catalog seeder (Task #003)..." -ForegroundColor Yellow
        python seed_cards.py
        Write-Host "[+] Master card catalog successfully seeded and updated." -ForegroundColor Green
    } else {
        Write-Host "[-] Warning: seed_cards.py not found. Skipping seeder step." -ForegroundColor Yellow
    }
} else {
    Write-Host "[+] Skipping seeder step as requested (-SkipSeeder)." -ForegroundColor DarkGray
}

Write-Host "==================================================" -ForegroundColor Cyan
Write-Host " Pipeline successfully completed!" -ForegroundColor Green
Write-Host " Run 'uvicorn main:app --reload --port 8000' to start the server." -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Cyan
