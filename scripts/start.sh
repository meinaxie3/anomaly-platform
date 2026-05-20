#!/usr/bin/env bash
# start.sh — launch the full Anomaly Platform stack
#
# Prerequisites:
#   - Docker (with compose v2)
#   - uv  (https://docs.astral.sh/uv/)
#   - Node.js >= 18 + npm
#   - .env file at repo root  (cp .env.example .env)
#
# Usage:
#   cd anomaly-platform
#   bash scripts/start.sh
#
# Each service runs in the background; logs go to logs/<service>.log.
# Ctrl-C or run:  bash scripts/stop.sh  to shut everything down.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOGS="$ROOT/logs"
mkdir -p "$LOGS"

step() { echo; echo "==> $*"; }
log_file() { echo "$LOGS/$1.log"; }

# ── 1. Infrastructure ────────────────────────────────────────────────────────
step "Starting infrastructure (Postgres, Redis, MinIO)..."
docker compose -f "$ROOT/infra/docker-compose.yml" up -d --wait
echo "Infrastructure healthy."

# ── 2. Python services ───────────────────────────────────────────────────────
declare -A PIDS=()

start_python() {
    local name="$1"; shift
    local cmd="$*"
    step "Starting $name..."
    cd "$ROOT"
    $cmd > "$(log_file "$name")" 2>&1 &
    PIDS[$name]=$!
    echo "  PID ${PIDS[$name]} → logs/$name.log"
}

start_python ingestion     uv run ingestion
start_python consumer      uv run consumer
start_python inference     uv run inference
start_python alerts        uv run alerts
start_python dashboard-api uv run dashboard

# ── 3. React dashboard ───────────────────────────────────────────────────────
step "Installing dashboard dependencies and starting dev server..."
cd "$ROOT/services/dashboard"
npm install --silent
npm run dev > "$(log_file "dashboard-ui")" 2>&1 &
PIDS[dashboard-ui]=$!
echo "  PID ${PIDS[dashboard-ui]} → logs/dashboard-ui.log"

# ── 4. Load generator (optional) ────────────────────────────────────────────
cd "$ROOT"
read -r -p $'\nStart load generator? [y/N] ' run_lg
if [[ "${run_lg,,}" == "y" ]]; then
    step "Starting load generator..."
    uv run load-gen --mode http --ingestion-url http://localhost:8001 \
        > "$(log_file "load-gen")" 2>&1 &
    PIDS[load-gen]=$!
    echo "  PID ${PIDS[load-gen]} → logs/load-gen.log"
fi

# ── 5. Summary ───────────────────────────────────────────────────────────────
cat <<EOF

All services running.

  Ingestion API   http://localhost:8001/docs
  Inference API   http://localhost:8002/docs
  Dashboard API   http://localhost:8003/docs
  React UI        http://localhost:5173
  MinIO console   http://localhost:9001  (minio / minio123)

Logs:  tail -f $LOGS/<service>.log
Stop:  bash scripts/stop.sh   (or kill the PIDs listed above)
EOF

# Write PID file so stop.sh can clean up
printf '%s\n' "${!PIDS[@]}" > "$LOGS/.pids"
for name in "${!PIDS[@]}"; do
    echo "${PIDS[$name]} $name"
done >> "$LOGS/.pids"

# Keep script alive so Ctrl-C kills children
wait
