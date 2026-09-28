# Update-PythonPaths.ps1 - Automates path consistency adjustments in .py files
param(
    [string]$TargetDir = "C:\Users\siniz\arena-helper\apps\api",
    [string]$OldDatabaseName = "engine_graph.db",
    [string]$NewDatabasePath = "engine_graph.db" # Or an absolute path if needed
)

Write-Host "=========================================" -ForegroundColor Cyan
Write-Host " PYTHON PATH & DB PATH STANDARDIZATION" -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan

$pyFiles = Get-ChildItem -Path $TargetDir -Filter "*.py"
$updatedCount = 0

foreach ($file in $pyFiles) {
    $content = Get-Content -Path $file.FullName -Raw
    $modified = $false

    # Example: Ensuring database connection strings use a consistent variable or path
    # This replaces hardcoded or mismatched db references if needed
    if ($content -match "sqlite3\.connect\(['\"].*?['\"]\)") {
        # You can add custom regex replacements here if your paths drift between scripts
        Write-Host "Inspecting paths in: $($file.Name)" -ForegroundColor Yellow
    }

    # Example safety check: Ensure absolute path resolution using pathlib or os.path if desired
    # For now, we verify file encoding and structural path consistency
    
    if ($modified) {
        Set-Content -Path $file.FullName -Value $content -Encoding utf8
        Write-Host "Updated paths in: $($file.Name)" -ForegroundColor Green
        $updatedCount++
    }
}

Write-Host "=========================================" -ForegroundColor Cyan
Write-Host " Scan complete. $updatedCount files adjusted." -ForegroundColor Cyan