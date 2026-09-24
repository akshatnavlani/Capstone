# Scheduled entry point for the ingestion pipeline — run daily via Windows Task
# Scheduler (see ORCHESTRATION.md for why Task Scheduler was chosen over Hermes).
# Runs all three platforms sequentially against the curated target list, logging to
# a dated file. Sequential, not parallel, by design: YouTube's quota-based API could
# run alongside the others safely, but Instagram/Reddit both go through the same
# Chrome session (OPENCLI_PROFILE) — running them concurrently from a scheduled task
# would race on that single browser session the same way parallel sub-agents against
# one platform would, so this script keeps them serialized regardless.

$ErrorActionPreference = "Continue"
$repoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$scriptDir = $PSScriptRoot
$py = "C:\Users\Sonic\AppData\Local\Programs\Python\Python314\python.exe"
$env:PATH += ";C:\Users\Sonic\AppData\Roaming\Python\Python314\Scripts"

$logDir = Join-Path $scriptDir "logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$logFile = Join-Path $logDir ("run_{0}.log" -f (Get-Date -Format "yyyyMMdd_HHmmss"))

Set-Location $scriptDir

"=== Pipeline run started $(Get-Date -Format o) ===" | Tee-Object -FilePath $logFile -Append

foreach ($platform in @("youtube", "instagram", "reddit")) {
    "--- $platform ---" | Tee-Object -FilePath $logFile -Append
    & $py orchestrator.py --platform $platform --target-list target_list.json 2>&1 |
        Tee-Object -FilePath $logFile -Append
}

"=== Pipeline run finished $(Get-Date -Format o) ===" | Tee-Object -FilePath $logFile -Append
