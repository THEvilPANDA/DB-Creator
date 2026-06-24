#!/usr/bin/env bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$SCRIPT_DIR")"
echo "Stopping DB Creator..."
cd "$ROOT"
docker compose down
echo "Done."
