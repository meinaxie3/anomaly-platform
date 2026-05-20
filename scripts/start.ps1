#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Start the full Anomaly Platform stack in separate windows.

.DESCRIPTION
    Starts infrastructure (Docker), then launches each Python service and the
    React dev server in separate PowerShell windows so you can see their logs.

    Prerequisites:
      - Docker Desktop running
      - uv installed  (https://docs.astral.sh/uv/)
      - Node.js >= 18 and npm installed (for the dashboard)
      - .env file present at the repo root  (copy .env.example to get started)

.EXAMPLE
    cd anomaly-platform
    .\scripts\start.ps1
#>

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$Root = Split-Path $PSScriptRoot -Parent

function Write-Step { param([string]$msg) Write-Host "`n==> $msg" -ForegroundColor Cyan }
function Invoke-Service {
    param([string]$Title, [string]$Command)
    Start-Process powershell -ArgumentList "-NoExit", "-Command",
        "cd '$Root'; $Command" -WindowStyle Normal
}

# ── 1. Infrastructure ────────────────────────────────────────────────────────
Write-Step "Starting infrastructure (Postgres, Redis, MinIO)..."
Push-Location $Root
docker compose -f infra/docker-compose.yml up -d --wait
if ($LASTEXITCODE -ne 0) { throw "docker compose failed" }
Pop-Location
Write-Host "Infrastructure healthy." -ForegroundColor Green

# ── 2. Python services ───────────────────────────────────────────────────────
$services = @(
    @{ Title = "ingestion";    Command = "uv run ingestion" },
    @{ Title = "consumer";     Command = "uv run consumer" },
    @{ Title = "inference";    Command = "uv run inference" },
    @{ Title = "alerts";       Command = "uv run alerts" },
    @{ Title = "dashboard-api";Command = "uv run dashboard" }
)

foreach ($svc in $services) {
    Write-Step "Starting $($svc.Title)..."
    Invoke-Service -Title $svc.Title -Command $svc.Command
    Start-Sleep -Seconds 1
}

# ── 3. React dashboard ───────────────────────────────────────────────────────
Write-Step "Starting React dev server..."
Invoke-Service -Title "dashboard-ui" -Command "cd services\dashboard; npm install; npm run dev"

# ── 4. Load generator (optional) ────────────────────────────────────────────
$runLoadGen = Read-Host "`nStart load generator? [y/N]"
if ($runLoadGen -eq 'y') {
    Write-Step "Starting load generator..."
    Invoke-Service -Title "load-gen" -Command "uv run load-gen --mode http --ingestion-url http://localhost:8001"
}

Write-Host @"

All services launched in separate windows.

  Ingestion API   http://localhost:8001/docs
  Inference API   http://localhost:8002/docs
  Dashboard API   http://localhost:8003/docs
  React UI        http://localhost:5173
  MinIO console   http://localhost:9001  (minio / minio123)

To stop everything:  docker compose -f infra/docker-compose.yml down
"@ -ForegroundColor Green
