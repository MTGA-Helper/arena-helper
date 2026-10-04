New-Item -ItemType Directory -Force -Path docs
Set-Content -Path docs\reconstruction-report.md -Value (Get-Clipboard)
