# Run-LocalAPI.ps1
Set-Location "C:\Users\siniz\arena-helper"
if (!(Test-Path "venv")) {
    python -m venv venv
}
& ".\venv\Scripts\Activate.ps1"
pip install -r apps/api/requirements.txt | Out-Null
Set-Location "apps/api"
uvicorn main:app --reload --host 127.0.0.1 --port 8000
