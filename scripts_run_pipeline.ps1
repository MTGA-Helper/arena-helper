# ==============================================================================
# Script Name: run_pipeline.ps1
# Accomplishment: Automates the Deck Evidence Engine workflow in PowerShell.
# Ensures correct directory context, logs matches, and generates evidence cards.
# ==============================================================================

param(
    [string]$Action = "generate", # "log" or "generate"
    [string]$Deck = "MWA-001",
    [string]$Result = "WIN",
    [string]$Rank = "Platinum",
    [int]$Turns = 7,
    [string]$Opponent = "Mono-Red"
)

# Ensure we are running from the project root
$targetDir = "$HOME\arena-helper"
if (Test-Path $targetDir) {
    Set-Location $targetDir
} else {
    Write-Host "[-] Warning: $targetDir not found. Using current location: $(Get-Location)" -ForegroundColor Yellow
}

Write-Host "[+] Current Working Directory: $(Get-Location)" -ForegroundColor Cyan

# Verify scripts directory exists
if (-not (Test-Path "scripts")) {
    Write-Host "[-] Error: 'scripts' folder not found in current directory." -ForegroundColor Red
    exit 1
}

if ($Action -eq "log") {
    Write-Host "[+] Logging match for deck $Deck ($Result vs $Opponent)..." -ForegroundColor Green
    python scripts\log_match.py --deck $Deck --result $Result --rank $Rank --turns $Turns --opponent $Opponent
} else {
    Write-Host "[+] Generating Evidence Card for Benchmark: $Deck..." -ForegroundColor Green
    python scripts\generate_evidence_card.py $Deck
}
