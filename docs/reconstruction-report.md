Set-Content -Path docs\reconstruction-report.md -Value (Get-Clipboard)
git add docs/reconstruction-report.md
git commit -m "docs(reconstruction): update report to v1.4 integrating live runtime OpenAPI route verification"
