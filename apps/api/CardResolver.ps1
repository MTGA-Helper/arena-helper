$global:CardIdMap = @{
    87246 = @{ Name = "Deep-Cavern Bat"; Type = "Creature"; MV = 2 }
    91635 = @{ Name = "Iridescent Vinelasher"; Type = "Creature"; MV = 1 }
    90455 = @{ Name = "Tinybones, the Pickpocket"; Type = "Creature"; MV = 1 }
    93771 = @{ Name = "Preacher of the Schism"; Type = "Creature"; MV = 3 }
    95195 = @{ Name = "Swamp"; Type = "Land"; MV = 0 }
    92199 = @{ Name = "Gixian Infiltrator"; Type = "Creature"; MV = 2 }
    87489 = @{ Name = "Vein Ripper"; Type = "Creature"; MV = 6 }
}

function Convert-CardIds {
    param([int[]]$Ids)
    foreach ($id in $Ids) {
        if ($global:CardIdMap.ContainsKey($id)) {
            $global:CardIdMap[$id].Name
        } else {
            "Unknown ($id)"
        }
    }
}
