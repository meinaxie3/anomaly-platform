#!/usr/bin/env bash
# stop.sh — tear down all services started by start.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOGS="$ROOT/logs"

step() { echo; echo "==> $*"; }

step "Stopping Python services and dev server..."
if [[ -f "$LOGS/.pids" ]]; then
    while IFS=' ' read -r pid name; do
        if kill -0 "$pid" 2>/dev/null; then
            echo "  Stopping $name (PID $pid)"
            kill "$pid" 2>/dev/null || true
        fi
    done < "$LOGS/.pids"
    rm -f "$LOGS/.pids"
else
    echo "  No PID file found — nothing to kill."
fi

step "Stopping Docker infrastructure..."
docker compose -f "$ROOT/infra/docker-compose.yml" down
echo "Done."
