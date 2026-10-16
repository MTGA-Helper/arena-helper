# ==============================================================================
# Script Name: inspect_arena.ps1
# Accomplishment: Scans the local arena-helper repository for existing database files,
# inspects table schemas for matches, and verifies SQLite connections.
# ==============================================================================

Write-Host "[+] Scanning for SQLite databases in repository..." -ForegroundColor Cyan

$databases = Get-ChildItem -Recurse -Filter "*.db"
foreach ($db in $databases) {
    Write-Host "`nFound Database: $($db.FullName)" -ForegroundColor Green
    try {
        # Query sqlite_master to list tables
        $tables = & python -c "import sqlite3; conn = sqlite3.connect(r'$($db.FullName)'); cursor = conn.cursor(); cursor.execute("SELECT name FROM sqlite_master WHERE type='table';"); print([row[0] for row in cursor.fetchall()]); conn.close()"
        Write-Host "  - Tables: $tables" -ForegroundColor Yellow
    } catch {
        Write-Host "  - Could not query tables via Python." -ForegroundColor Red
    }
}
