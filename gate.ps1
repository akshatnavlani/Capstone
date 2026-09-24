# A2 pre-review gate — run this before any review, not during one.
# Fails loudly (nonzero exit + names the failed step) instead of letting a
# broken build surface in the demo. A3 canaries will extend this script later.
#
# Defaults assume the D:\Capstone-worktrees layout from AGENTS.md. For an
# assembled checkout (backend/ + ml/ + frontend/ side by side), pass -BRoot,
# -CRoot and -DRoot explicitly.
param(
    [string]$BRoot = "D:\Capstone-worktrees\track-b-ml-core",
    [string]$CRoot = "D:\Capstone-worktrees\track-c-fusion-backend",
    [string]$DRoot = "D:\Capstone-worktrees\track-d-frontend-app",
    [string]$DockerExe = "$env:LOCALAPPDATA\Programs\DockerDesktop\resources\bin\docker.exe",
    [int]$SmokePort = 18000
)

$ErrorActionPreference = "Stop"
$failed = @()

function Invoke-GateStep {
    param([string]$Name, [scriptblock]$Body)
    Write-Host ""
    Write-Host "### $Name"
    Push-Location $DRoot
    try {
        & $Body
        if ($LASTEXITCODE -ne 0) { throw "exit $LASTEXITCODE" }
        Write-Host "PASS: $Name"
    }
    catch {
        Write-Host "FAIL: $Name -- $($_.Exception.Message)"
        $script:failed += $Name
    }
    finally {
        Pop-Location
    }
}

Invoke-GateStep "track-b pytest" {
    Push-Location $BRoot
    try { & "$BRoot\.venv\Scripts\python.exe" -m pytest tests/ -q }
    finally { Pop-Location }
}

Invoke-GateStep "track-c pytest" {
    Push-Location $CRoot
    try { & "$CRoot\backend\.venv\Scripts\python.exe" -m pytest backend/tests -q }
    finally { Pop-Location }
}

Invoke-GateStep "frontend lint" {
    Push-Location "$DRoot\frontend"
    try { & npm run lint }
    finally { Pop-Location }
}

Invoke-GateStep "frontend build" {
    Push-Location "$DRoot\frontend"
    try { & npm run build }
    finally { Pop-Location }
}

Invoke-GateStep "docker backend smoke" {
    if (-not (Test-Path -LiteralPath $DockerExe)) { throw "docker CLI not found at $DockerExe" }
    $curl = (Get-Command curl.exe -ErrorAction SilentlyContinue).Source
    if (-not $curl) { throw "curl.exe not found (Windows 10+ ships it; PATH broken?)" }
    & $DockerExe info 2>$null | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "docker daemon unreachable (is Docker Desktop running?)" }
    & $DockerExe build -f "$DRoot\backend\Dockerfile" -t capstone-backend:gate "$DRoot"
    if ($LASTEXITCODE -ne 0) { throw "docker build failed" }
    & $DockerExe rm -f capstone-gate 2>$null | Out-Null
    & $DockerExe run -d --name capstone-gate -p "${SmokePort}:8000" capstone-backend:gate | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "docker run failed" }
    try {
        # NOTE: Invoke-WebRequest is deliberately NOT used here — under a
        # non-interactive shell it can raise a host prompt instead of
        # connecting. curl.exe has no such behavior.
        $health = ""
        for ($i = 0; $i -lt 30; $i++) {
            Start-Sleep -Seconds 2
            $health = & $curl -s -o NUL -w "%{http_code}" --max-time 5 "http://127.0.0.1:${SmokePort}/health" 2>$null
            if ($health -eq "200") { break }
        }
        if ($health -ne "200") { throw "/health never returned 200 (last: $health)" }
        $tmpBody = [System.IO.Path]::GetTempFileName()
        try {
            @{ product_category = "fitness apparel"; budget = 5000000 } | ConvertTo-Json -Compress | Set-Content -LiteralPath $tmpBody -NoNewline
            $rec = & $curl -s -o NUL -w "%{http_code}" --max-time 30 -X POST -H "Content-Type: application/json" --data-binary "@$tmpBody" "http://127.0.0.1:${SmokePort}/recommendations" 2>$null
        }
        finally {
            Remove-Item -LiteralPath $tmpBody -Force -ErrorAction SilentlyContinue
        }
        if ($rec -ne "200") { throw "/recommendations returned $rec" }
        Write-Host "/health 200 + /recommendations 200 (placeholder-mode smoke: ml/ not baked in by design)"
    }
    finally {
        & $DockerExe stop capstone-gate 2>$null | Out-Null
        & $DockerExe rm capstone-gate 2>$null | Out-Null
    }
}

Write-Host ""
if ($failed.Count -gt 0) {
    Write-Host ("GATE RED: " + ($failed -join ", "))
    exit 1
}
Write-Host "GATE GREEN: pytest B + pytest C + lint + build + docker smoke all pass"
