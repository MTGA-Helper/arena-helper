function Find-LogPattern {

    param(
        [string]$Pattern,
        [string]$LogPath = "$env:USERPROFILE\AppData\LocalLow\Wizards Of The Coast\MTGA\Player.log"
    )

    if (-not (Test-Path $LogPath)) {
        Write-Error "Player.log not found at: $LogPath"
        return
    }

    Select-String `
        -Path $LogPath `
        -Pattern $Pattern |
        Select-Object -First 25 |
        Select-Object LineNumber, Line
}
