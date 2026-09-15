# Arena Helper Architecture v1.0

## Product Mission
> **Arena Helper does not recommend the strongest deck. Arena Helper recommends the strongest deck a player can realistically build, afford, and continue playing.**

## Core Formula
* **Collection = Truth** (The player's actual reality)
* **Meta = Context** (The competitive landscape)
* **Recommendation Engine = Decision Layer** (The personalized bridge)

---

## Domain Model
1. **Users & Economy**: `users`, `wildcard_inventories`, `collection_import_logs`
2. **Canonical Card Data**: `cards`, `card_prints`, `card_legality`
3. **Intelligence & Metagame**: `card_intelligence`, `archetypes`, `card_archetype_affinities`, `meta_snapshots`
4. **Deck Infrastructure**: `decks`, `deck_cards`
5. **User Inventory**: `user_collections` (tied directly to canonical `cards`)

---

## Data Flow
```text
Scryfall Bulk Data \
                    --> cards / card_prints / card_legality
MTGA Catalog Mappings /

Collection.csv -> Collection Importer -> user_collections

Meta Sources -> decks / deck_cards / meta_snapshots

[UserCollection + Decks + Meta + Wildcards] -> Recommendation Engine

Set-Content -Path "run-pipeline.ps1" -Value @'
param(
    [switch]$SkipSeeder
)

$ErrorActionPreference = "Stop"

Write-Host "==================================================" -ForegroundColor Cyan
Write-Host " Arena Helper API - Automation Pipeline" -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Cyan

# 1. Verify virtual environment activation
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

# 2. Ensure required python packages are present
Write-Host "[+] Checking / installing required packages..." -ForegroundColor Yellow
pip install -r requirements.txt --quiet --disable-pip-version-check
pip install PyJWT structlog pydantic-settings python-multipart httpx --quiet --disable-pip-version-check

# 3. Verify .env file and configuration
if (-not (Test-Path ".env")) {
    Write-Host "[-] Error: .env configuration file missing!" -ForegroundColor Red
    exit 1
}
Write-Host "[+] Environment configuration file detected." -ForegroundColor Green

# 4. Initialize Database Models & Tables
Write-Host "[+] Verifying database connection and schema tables..." -ForegroundColor Yellow
python -c "import asyncio; from database import engine, Base; from models import *; async def init(): 
    async with engine.begin() as conn: await conn.run_sync(Base.metadata.create_all)
asyncio.run(init())"
Write-Host "[+] Database tables verified successfully." -ForegroundColor Green

# 5. Run Idempotent Card Seeder (Task #003)
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
