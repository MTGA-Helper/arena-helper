function Get-CastActionsFromLog {
    param([string]$LogPath = "$env:USERPROFILE\AppData\LocalLow\Wizards Of The Coast\MTGA\Player.log")

    if (-not (Test-Path $LogPath)) {
        Write-Error "Player.log not found at: $LogPath"
        return
    }

    $lines = Get-Content $LogPath
    $casts = @()
    $insideCastBlock = $false

    foreach ($line in $lines) {
        if ($line -match '"actionType"\s*:\s*"ActionType_Cast"') {
            $insideCastBlock = $true
            continue
        }

        if ($insideCastBlock) {
            if ($line -match '"grpId"\s*:\s*(\d+)') {
                $casts += [int]$Matches[1]
                $insideCastBlock = $false
            }
            # Reset if we hit a closing bracket or separator without finding a grpId in this object
            if ($line -match '^\s*[\}\]]\s*,?$') {
                $insideCastBlock = $false
            }
        }
    }

    return Convert-CardIds $casts
}
