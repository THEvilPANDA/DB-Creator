#!/usr/bin/env bash
# Stop all DB Creator processes
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$SCRIPT_DIR")"

echo "Stopping DB Creator..."

# Kill backend/frontend by saved PID
for pidfile in "$ROOT/.backend.pid" "$ROOT/.frontend.pid"; do
  if [ -f "$pidfile" ]; then
    pid=$(cat "$pidfile")
    kill "$pid" 2>/dev/null && echo "  Killed PID $pid" || true
    rm -f "$pidfile"
  fi
done

# Also kill by port in case PIDs drifted
for port in 8000 5173; do
  fuser -k "${port}/tcp" 2>/dev/null && echo "  Freed port $port" || true
done

# Stop Docker services
cd "$ROOT"
docker compose stop
echo "  Docker services stopped"
echo "Done."
