# ==============================================================================
# Script Name: run_pipeline.ps1
# Accomplishment: PowerShell wrapper for the Deck Evidence Engine pipeline.
# Automatically resolves project path and delegates to Python execution.
# ==============================================================================

param(
    [string]$Action = "generate",
    [string]$Deck = "MWA-001",
    [string]$Result = "WIN",
    [string]$Rank = "Platinum",
    [int]$Turns = 7,
    [string]$Opponent = "Mono-Red"
)

# Navigate to user home arena-helper if it exists, or stay in current
$targetDir = "$HOME\arena-helper"
if (Test-Path $targetDir) {
    Set-Location $targetType = $targetDir
}

$scriptPath = Join-Path (Get-Location) "scripts\run_pipeline.py"
if (-not (Test-Path $scriptPath)) {
    # Check if we are inside scripts already
    if (Test-Path "run_pipeline.py") {
        $scriptPath = "run_pipeline.py"
    } else {
        Write-Host "[-] Error: run_pipeline.py not found. Please run from project root." -ForegroundColor Red
        exit 1
    }
}

python $scriptPath --action $Action --deck $Deck --result $Result --rank $Rank --turns $Turns --opponent $Opponent
