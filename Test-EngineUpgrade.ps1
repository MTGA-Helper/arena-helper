# Test-EngineUpgrade.ps1 - Engine-Centric V2 Upgrade Advisor
param(
    [Parameter(Mandatory=$true)]
    [string]$DeckName,
    [string]$CollectionPath = "collection.csv"
)

if (-not (Test-Path $CollectionPath)) {
    Write-Error "Collection file '$CollectionPath' not found in current directory!"
    exit
}

# 1. Load user collection into a hash table for fast lookups
$collectionData = Import-Csv $CollectionPath
$ownedCards = @{}
foreach ($row in $collectionData) {
    if ($row.Name -and $row.Count) {
        $ownedCards[$row.Name.Trim()] = [int]$row.Count
    }
}

# 2. Define your engine archetypes, connection scores, and hub roles
$engines = @{
    "orzhov-drain" = @{
        MustProtect = "Bloodletter of Aclazotz"
        HubScore    = 9
        Resilience  = 9
        CorePieces  = @(
            [PSCustomObject]@{ Name = "Authority of the Consuls"; Role = "Trigger Generator" },
            [PSCustomObject]@{ Name = "Starscape Cleric"; Role = "Converter" },
            [PSCustomObject]@{ Name = "Marauding Blight-Priest"; Role = "Converter" },
            [PSCustomObject]@{ Name = "Bloodthirsty Conqueror"; Role = "Converter" },
            [PSCustomObject]@{ Name = "South Wind Avatar"; Role = "Amplifier" },
            [PSCustomObject]@{ Name = "Sheltered by Ghosts"; Role = "Protector" },
            [PSCustomObject]@{ Name = "Bloodletter of Aclazotz"; Role = "Engine Hub / Amplifier" }
        )
    }
    "landfall-hydra" = @{
        MustProtect = "Mossborn Hydra"
        HubScore    = 10
        Resilience  = 6
        CorePieces  = @(
            [PSCustomObject]@{ Name = "Icetill Explorer"; Role = "Trigger Generator" },
            [PSCustomObject]@{ Name = "Fabled Passage"; Role = "Trigger Generator" },
            [PSCustomObject]@{ Name = "Escape Tunnel"; Role = "Trigger Generator" },
            [PSCustomObject]@{ Name = "Ride the Shoopuf"; Role = "Trigger Generator" },
            [PSCustomObject]@{ Name = "Sapling Nursery"; Role = "Engine Hub" },
            [PSCustomObject]@{ Name = "Bristly Bill"; Role = "Amplifier" },
            [PSCustomObject]@{ Name = "Mossborn Hydra"; Role = "Engine Hub / Payoff" }
        )
    }
}

$slug = $DeckName.ToLower().Replace(" ", "-")
if (-not $engines.ContainsKey($slug)) {
    Write-Host "Unknown deck archetype. Defaulting to 'orzhov-drain'." -ForegroundColor Yellow
    $slug = "orzhov-drain"
}

$engine = $engines[$slug]
$corePieces = $engine.CorePieces

# 3. Evaluate collection status
$ownedCount = 0
$activatedCards = @()
$missingPieces = @()

foreach ($piece in $corePieces) {
    if ($ownedCards.ContainsKey($piece.Name) -and $ownedCards[$piece.Name] -gt 0) {
        $ownedCount++
        $activatedCards += $piece.Name
    } else {
        $missingPieces += $piece.Name
    }
}

$completionPct = [Math]::Round(($ownedCount / $corePieces.Count) * 100, 1)

# 4. Determine Engine Status State
if ($completionPct -eq 100) {
    $status = "Fully Buildable"
} elseif ($completionPct -ge 80) {
    $status = "Engine Complete"
} elseif ($missingPieces.Count -eq 1) {
    $status = "One-Step Away"
} else {
    $status = "Engine Fragmented"
}

$missingStr = if ($missingPieces.Count -gt 0) { $missingPieces[0] } else { "None" }

# 5. Display V2 Recommendation Output
Write-Host "==================================================" -ForegroundColor Cyan
Write-Host " ARENA HELPER V2: ENGINE UPGRADE ADVISOR" -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Cyan
Write-Host "Deck Archetype   : $DeckName" -ForegroundColor White
Write-Host "Engine Status    : $status" -ForegroundColor $(if ($status -eq "One-Step Away" -or $status -eq "Engine Complete") { "Green" } else { "Yellow" })
Write-Host "Engine Completion: $completionPct%" -ForegroundColor Yellow
Write-Host "Connection Score : $($engine.HubScore)/10" -ForegroundColor Cyan
Write-Host "Resilience Score : $($engine.Resilience)/10" -ForegroundColor Cyan
Write-Host "Must Protect     : $($engine.MustProtect)" -ForegroundColor Magenta
Write-Host "--------------------------------------------------" -ForegroundColor Cyan
Write-Host "RECOMMENDED ACTION:" -ForegroundColor Green
if ($missingStr -ne "None") {
    Write-Host "Craft '$missingStr'." -ForegroundColor White
    Write-Host "Why? Completes the loop, instantly activating $($activatedCards.Count) cards already owned in your collection with a Connection Score of $($engine.HubScore)." -ForegroundColor Gray
} else {
    Write-Host "Engine is fully assembled and ready to pilot!" -ForegroundColor White
}
Write-Host "==================================================" -ForegroundColor Cyan
