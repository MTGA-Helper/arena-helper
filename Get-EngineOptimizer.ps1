# Get-EngineOptimizer.ps1 - V2.2 Dynamic Engine & Wildcard Optimizer
param(
    [string]$CollectionPath = "collection.csv"
)

if (-not (Test-Path $CollectionPath)) {
    Write-Error "Collection file '$CollectionPath' not found in current directory!"
    exit
}

$collectionData = Import-Csv $CollectionPath
$ownedCards = @{}
foreach ($row in $collectionData) {
    if ($row.Name -and $row.Count) {
        $ownedCards[$row.Name.Trim()] = [int]$row.Count
    }
}

$engines = @{
    "Orzhov Drain" = @{
        ConnectionScore = 9
        ProtectionScore = 9
        CorePieces = @(
            "Authority of the Consuls",
            "Starscape Cleric",
            "Marauding Blight-Priest",
            "Bloodthirsty Conqueror",
            "South Wind Avatar",
            "Sheltered by Ghosts",
            "Bloodletter of Aclazotz"
        )
    }
    "Landfall Hydra" = @{
        ConnectionScore = 10
        ProtectionScore = 6
        CorePieces = @(
            "Icetill Explorer",
            "Fabled Passage",
            "Escape Tunnel",
            "Ride the Shoopuf",
            "Sapling Nursery",
            "Bristly Bill",
            "Mossborn Hydra"
        )
    }
    "Hare Tokens" = @{
        ConnectionScore = 8
        ProtectionScore = 7
        CorePieces = @(
            "Hare Apparent",
            "Skyknight Squire",
            "Essence Channeler",
            "Hinterland Sanctifier",
            "Ajani's Pridemate",
            "Lifecreed Duo"
        )
    }
}

$recommendations = @()

foreach ($deckName in $engines.Keys) {
    $engine = $engines[$deckName]
    $corePieces = $engine.CorePieces
    
    $ownedCount = 0
    $missingPieces = @()

    foreach ($card in $corePieces) {
        if ($ownedCards.ContainsKey($card) -and $ownedCards[$card] -gt 0) {
            $ownedCount++
        } else {
            $missingPieces += $card
        }
    }

    $completionPct = [Math]::Round(($ownedCount / $corePieces.Count) * 100, 1)
    $wildcardsNeeded = $missingPieces.Count
    
    if ($completionPct -eq 100) {
        $status = "Ready to Play"
    } elseif ($wildcardsNeeded -eq 1) {
        $status = "One Amplifier Away"
    } else {
        $status = "Engine Fragmented"
    }

    $recommendations += [PSCustomObject]@{
        Deck            = $deckName
        Completion      = $completionPct
        WildcardsNeeded = $wildcardsNeeded
        ConnectionGain  = if ($missingPieces.Count -gt 0) { $ownedCount } else { 0 }
        MissingCard     = if ($missingPieces.Count -gt 0) { $missingPieces[0] } else { "None" }
        ConnectionScore = $engine.ConnectionScore
        ProtectionScore = $engine.ProtectionScore
        Status          = $status
    }
}

$sortedRecommendations = $recommendations | Sort-Object -Property @{Expression="Completion"; Descending=$true}, @{Expression="ConnectionGain"; Descending=$true}

Write-Host "=========================================================" -ForegroundColor Cyan
Write-Host " ARENA HELPER V2.2: COLLECTION ENGINE OPPORTUNITIES" -ForegroundColor Cyan
Write-Host "=========================================================" -ForegroundColor Cyan

$rank = 1
foreach ($rec in $sortedRecommendations) {
    Write-Host "$rank. $($rec.Deck)" -ForegroundColor Green
    Write-Host "   Engine Completion : $($rec.Completion)% ($($rec.Status))" -ForegroundColor White
    Write-Host "   Wildcards Needed  : $($rec.WildcardsNeeded)" -ForegroundColor $(if ($rec.WildcardsNeeded -eq 0) { "Green" } else { "Yellow" })
    Write-Host "   Connection Gain   : +$($rec.ConnectionGain) owned pieces activated" -ForegroundColor Cyan
    Write-Host "   Scores            : Connection $($rec.ConnectionScore)/10 | Protection $($rec.ProtectionScore)/10" -ForegroundColor Gray
    if ($rec.MissingCard -ne "None") {
        Write-Host "   Top Craft Target  : $($rec.MissingCard)" -ForegroundColor Magenta
    }
    Write-Host "---------------------------------------------------------" -ForegroundColor DarkGray
    $rank++
}
