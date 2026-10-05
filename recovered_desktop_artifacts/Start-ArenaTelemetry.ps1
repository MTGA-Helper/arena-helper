# Start-ArenaTelemetry.ps1 - Final Production Telemetry Ingestion v4.1
$LogPath = "$env:USERPROFILE\AppData\LocalLow\Wizards Of The Coast\MTGA\Player.log"
$OutputDir = "MatchReports"
$ActiveDir = Join-Path $OutputDir "Active"

if (Test-Path "CardResolver.ps1") {
    . .\CardResolver.ps1
} else {
    Write-Error "CardResolver.ps1 not found in current directory!"
    exit
}

if (-not (Test-Path $OutputDir)) { New-Item -ItemType Directory -Path $OutputDir | Out-Null }
if (-not (Test-Path $ActiveDir)) { New-Item -ItemType Directory -Path $ActiveDir | Out-Null }

Write-Host "--- MTGA TELEMETRY ENGINE v4.1 ACTIVE ---" -ForegroundColor Cyan
Write-Host "Monitoring Log: $LogPath" -ForegroundColor Yellow

$script:CurrentMatch = @{
    MatchId       = $null
    Timestamp     = (Get-Date).ToString("yyyy-MM-ddTHH:mm:ss")
    MyPlayerName  = "owlensteed"
    MyTeamId      = $null
    MySeatId      = $null
    Opponent      = "Unknown Opponent"
    OpeningHand   = @()
    CardsCast     = @()
    WinningTeam   = $null
    Saved         = $false
}

$script:InstanceToGrpMap = @{}
$script:PendingInstanceId = $null
$script:LastPlayerSeen = $null
$script:PendingHandOwner = $null
$script:HandInstanceIds = @()

$script:lastLineCount = 0
if (Test-Path $LogPath) {
    $script:lastLineCount = (Get-Content $LogPath).Count
}

$watcher = [System.IO.FileSystemWatcher]::new()
$watcher.Path = [System.IO.Path]::GetDirectoryName($LogPath)
$watcher.Filter = [System.IO.Path]::GetFileName($LogPath)
$watcher.IncludeSubdirectories = $false
$watcher.EnableRaisingEvents = $true

$action = {
    param($sender, $e)
    Start-Sleep -Milliseconds 300

    try {
        if (-not (Test-Path $LogPath)) { return }
        $lines = Get-Content $LogPath -ErrorAction Stop

        if ($lines.Count -lt $script:lastLineCount) {
            $script:lastLineCount = 0
            $script:InstanceToGrpMap.Clear()
        }

        if ($lines.Count -le $script:lastLineCount) { return }

        $newLines = $lines[$script:lastLineCount..($lines.Count - 1)]
        $script:lastLineCount = $lines.Count

        $insideCastBlock = $false

        foreach ($line in $newLines) {
            # 1. Match Initialization
            if ($line -match 'Connecting to matchId\s+([0-9a-fA-F-]+)') {
                $matchedId = $Matches[1]
                if ($script:CurrentMatch.MatchId -ne $matchedId) {
                    if ($script:CurrentMatch.MatchId -and -not $script:CurrentMatch.Saved) {
                        Save-MatchReport
                    }

                    $script:CurrentMatch = @{
                        MatchId       = $matchedId
                        Timestamp     = (Get-Date).ToString("yyyy-MM-ddTHH:mm:ss")
                        MyPlayerName  = "owlensteed"
                        MyTeamId      = $null
                        MySeatId      = $null
                        Opponent      = "Unknown Opponent"
                        OpeningHand   = @()
                        CardsCast     = @()
                        WinningTeam   = $null
                        Saved         = $false
                    }
                    $script:InstanceToGrpMap.Clear()
                    $script:PendingInstanceId = $null
                    $script:LastPlayerSeen = $null
                    $script:PendingHandOwner = $null
                    $script:HandInstanceIds = @()

                    Write-Host "[TELEMETRY] Match session started: $matchedId" -ForegroundColor Cyan
                }
            }

            # 2. Resilient Player & Seat Binding
            if ($line -match '"playerName":\s*"([^"]+)"') {
                $detectedPlayer = $Matches[1]
                if ($detectedPlayer -ne $script:CurrentMatch.MyPlayerName -and $script:CurrentMatch.Opponent -eq "Unknown Opponent") {
                    $script:CurrentMatch.Opponent = $detectedPlayer
                }
                $script:LastPlayerSeen = $detectedPlayer
            }
            if ($line -match '"systemSeatId":\s*(\d+)') {
                $seatId = [int]$Matches[1]
                if ($script:LastPlayerSeen -eq $script:CurrentMatch.MyPlayerName) {
                    $script:CurrentMatch.MySeatId = $seatId
                }
            }
            if ($line -match '"teamId":\s*(\d+)') {
                $teamId = [int]$Matches[1]
                if ($script:LastPlayerSeen -eq $script:CurrentMatch.MyPlayerName) {
                    $script:CurrentMatch.MyTeamId = $teamId
                }
            }

            # 3. InstanceId -> GrpId Mapping
            if ($line -match '"instanceId":\s*(\d+)') {
                $script:PendingInstanceId = [int]$Matches[1]
            }
            elseif ($script:PendingInstanceId -and $line -match '"grpId":\s*(\d+)') {
                $script:InstanceToGrpMap[$script:PendingInstanceId] = [int]$Matches[1]
                $script:PendingInstanceId = $null
            }

            # 4. Seat-Safe Hand Zone Ownership Tracking
            if ($line -match '"ownerSeatId":\s*(\d+)') {
                $script:PendingHandOwner = [int]$Matches[1]
            }
            if ($line -match '"objectInstanceIds":\s*\[([^\]]+)\]' -and $script:PendingHandOwner -eq $script:CurrentMatch.MySeatId) {
                $script:HandInstanceIds = $Matches[1] -split ',' | ForEach-Object { $_.Trim() -as [int] }
            }

            # 5. Opening Hand Reconstruction upon Mulligan Acceptance
            if ($line -match '"decision":\s*"MulliganOption_AcceptHand"') {
                if ($script:HandInstanceIds.Count -gt 0 -and $script:CurrentMatch.OpeningHand.Count -eq 0) {
                    $resolvedHand = @()
                    foreach ($instId in $script:HandInstanceIds) {
                        if ($script:InstanceToGrpMap.ContainsKey($instId)) {
                            $grpId = $script:InstanceToGrpMap[$instId]
                            $cardName = if ($global:CardIdMap -and $global:CardIdMap.ContainsKey($grpId)) {
                                $global:CardIdMap[$grpId].Name
                            } else {
                                "Unknown ($grpId)"
                            }
                            $resolvedHand += $cardName
                        }
                    }
                    if ($resolvedHand.Count -gt 0) {
                        $script:CurrentMatch.OpeningHand = $resolvedHand
                        Write-Host "[TELEMETRY] Opening hand locked ($($resolvedHand.Count) cards)." -ForegroundColor Green
                    }
                }
            }

            # 6. Unfiltered Cast Tracking (Preserves duplicate frequency)
            if ($line -match '"actionType"\s*:\s*"ActionType_Cast"') {
                $insideCastBlock = $true
                continue
            }

            if ($insideCastBlock) {
                if ($line -match '"grpId"\s*:\s*(\d+)') {
                    $cardId = [int]$Matches[1]
                    $cardName = if ($global:CardIdMap -and $global:CardIdMap.ContainsKey($cardId)) { 
                        $global:CardIdMap[$cardId].Name 
                    } else { 
                        "Unknown ($cardId)" 
                    }
                    $script:CurrentMatch.CardsCast += $cardName
                    $insideCastBlock = $false
                }
                if ($line -match '^\s*[\}\]]\s*,?$') {
                    $insideCastBlock = $false
                }
            }

            # 7. Result Detection via winningTeamId
            if ($line -match '"winningTeamId"\s*:\s*(\d+)') {
                $script:CurrentMatch.WinningTeam = [int]$Matches[1]
                if ($script:CurrentMatch.MatchId -and -not $script:CurrentMatch.Saved) {
                    Save-MatchReport
                }
            }
        }

        if ($script:CurrentMatch.MatchId -and -not $script:CurrentMatch.Saved) {
            Save-ActiveState
        }
    }
    catch {}
}

function Save-ActiveState {
    $activeFile = Join-Path $ActiveDir "$($script:CurrentMatch.MatchId).json"
    $stateData = [PSCustomObject]@{
        Status      = "InProgress"
        MatchId     = $script:CurrentMatch.MatchId
        Timestamp   = $script:CurrentMatch.Timestamp
        Opponent    = $script:CurrentMatch.Opponent
        OpeningHand = $script:CurrentMatch.OpeningHand
        CardsCast   = $script:CurrentMatch.CardsCast
    }
    $stateData | ConvertTo-Json -Depth 4 | Set-Content $activeFile -ErrorAction SilentlyContinue
}

function Save-MatchReport {
    if (-not $script:CurrentMatch.MatchId) { return }

    $reportPath = Join-Path $OutputDir "$($script:CurrentMatch.MatchId).json"
    $activeFile = Join-Path $ActiveDir "$($script:CurrentMatch.MatchId).json"
    
    $result = "Loss"
    if ($script:CurrentMatch.MyTeamId -and $script:CurrentMatch.WinningTeam -eq $script:CurrentMatch.MyTeamId) {
        $result = "Win"
    }

    $matchData = [PSCustomObject]@{
        MatchId     = $script:CurrentMatch.MatchId
        Timestamp   = $script:CurrentMatch.Timestamp
        Opponent    = $script:CurrentMatch.Opponent
        OpeningHand = $script:CurrentMatch.OpeningHand
        CardsCast   = $script:CurrentMatch.CardsCast
        Result      = $result
    }

    $matchData | ConvertTo-Json -Depth 4 | Set-Content $reportPath
    $script:CurrentMatch.Saved = $true

    if (Test-Path $activeFile) { Remove-Item $activeFile -Force }

    Write-Host "[TELEMETRY] Match saved -> $($script:CurrentMatch.MatchId).json | $result vs $($script:CurrentMatch.Opponent)" -ForegroundColor Green
    Update-TelemetryIndex
}

function Update-TelemetryIndex {
    $reportFiles = Get-ChildItem (Join-Path $OutputDir "*.json") | Where-Object { $_.Name -ne "index.json" }
    $totalMatches = $reportFiles.Count
    $wins = 0

    foreach ($file in $reportFiles) {
        try {
            $content = Get-Content $file.FullName -Raw | ConvertFrom-Json
            if ($content.Result -eq "Win") { $wins++ }
        } catch {}
    }

    $losses = $totalMatches - $wins
    $winRate = if ($totalMatches -gt 0) { [Math]::Round(($wins / $totalMatches) * 100, 2) } else { 0.0 }

    $indexData = [PSCustomObject]@{
        Matches = $totalMatches
        Wins    = $wins
        Losses  = $losses
        WinRate = $winRate
    }

    $indexData | ConvertTo-Json -Depth 3 | Set-Content (Join-Path $OutputDir "index.json")
}

Register-ObjectEvent $watcher "Changed" -Action $action | Out-Null

Write-Host "Telemetry collection v4.1 active. Go play your matches and validate the JSON output!" -ForegroundColor Green
while ($true) { Start-Sleep -Seconds 1 }
