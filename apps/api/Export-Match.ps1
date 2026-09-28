function Export-SegmentedMatchReports {
    param([string]$LogPath = "$env:USERPROFILE\AppData\LocalLow\Wizards Of The Coast\MTGA\Player.log")

    if (-not (Test-Path $LogPath)) {
        Write-Error "Player.log not found at: $LogPath"
        return
    }

    if (-not (Test-Path "MatchReports")) {
        New-Item -ItemType Directory -Path "MatchReports" | Out-Null
    }

    $lines = Get-Content $LogPath
    $matchId = $null
    $opponent = "Unknown Opponent"
    $openingHand = @()
    $cardsCast = @()
    $inMatch = $false

    # Simple pass to extract match metadata and session tokens
    for ($i = 0; $i -lt $lines.Count; $i++) {
        if ($lines[$i] -match 'Connecting to matchId\s+([0-9a-fA-F-]+)') {
            $matchId = $Matches[1]
        }
        if ($lines[$i] -match '"playerName"\s*:\s*"([^"]+)"') {
            # Capture non-self player name if available in room config
            # (For now we fallback to placeholder or room parser)
        }
    }

    Write-Host "Discovered Match ID: $matchId" -ForegroundColor Cyan
}
