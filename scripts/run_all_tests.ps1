# Runs every test suite of the project, for the report's test screenshot (12 Nov 2026).
#   powershell -ExecutionPolicy Bypass -File scripts\run_all_tests.ps1
$ErrorActionPreference = "Continue"
Set-Location (Split-Path $PSScriptRoot -Parent)
$env:PYTHONIOENCODING = "utf-8"
Write-Host "`n=== 1/4  ML and analysis tests (tests/) ===" -ForegroundColor Cyan
venv\Scripts\python.exe -m pytest tests -q -p no:warnings
Write-Host "`n=== 2/4  Backend API tests (backend/tests/) ===" -ForegroundColor Cyan
venv\Scripts\python.exe -m pytest backend\tests -q -p no:warnings
Write-Host "`n=== 3/4  Data collection tests (scripts/ingestion/) ===" -ForegroundColor Cyan
venv\Scripts\python.exe -m pytest scripts\ingestion -q -p no:warnings
Write-Host "`n=== 4/4  Frontend: TypeScript type check and ESLint ===" -ForegroundColor Cyan
Set-Location frontend
npx tsc --noEmit; if ($LASTEXITCODE -eq 0) { Write-Host "TypeScript: no errors" -ForegroundColor Green }
npx eslint .; if ($LASTEXITCODE -eq 0) { Write-Host "ESLint: no errors" -ForegroundColor Green }
Set-Location ..
Write-Host "`n=== done ===" -ForegroundColor Cyan
