#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$SCRIPT_DIR")"

GREEN='\033[0;32m'; CYAN='\033[0;36m'; RED='\033[0;31m'; NC='\033[0m'
ok()   { echo -e "  ${GREEN}OK${NC}  $1"; }
fatal(){ echo -e "\n  ${RED}ERROR:${NC} $1"; exit 1; }

echo "╔══════════════════════════════════════════════════════════════════╗"
echo "║              DB Creator — Setup & Start                         ║"
echo "╚══════════════════════════════════════════════════════════════════╝"

# 1. backend/.env
BACKEND_ENV="$ROOT/backend/.env"
if [ ! -f "$BACKEND_ENV" ]; then
  cat > "$BACKEND_ENV" <<'EOF'
DATABASE_URL=postgresql+asyncpg://dbcreator:dbcreator@localhost:5432/dbcreator
REDIS_URL=redis://localhost:6379/0
FERNET_KEY=YnF46Ea_bY5OsdxJ2xOGoAo471HkEJslQfMpTxaRsNU=
DEBUG=false
ENVIRONMENT=development
ADMIN_KEY=dev-admin-key
JWT_SECRET=dev-jwt-secret-change-in-production
DEFAULT_ADMIN_PASSWORD=admin123
EOF
  ok "Created backend/.env"
else
  ok "backend/.env exists"
fi

# 2. frontend/.env
FRONTEND_ENV="$ROOT/frontend/.env"
if [ ! -f "$FRONTEND_ENV" ]; then
  echo "VITE_ADMIN_KEY=dev-admin-key" > "$FRONTEND_ENV"
  ok "Created frontend/.env"
else
  ok "frontend/.env exists"
fi

# 3. Docker check
command -v docker &>/dev/null || fatal "Docker not found. Install Docker Engine and re-run."
docker info &>/dev/null        || fatal "Docker is not running. Start it and re-run."
ok "Docker running"

# 4. Start
cd "$ROOT"
echo ""
echo -e "  ${CYAN}Starting all services (first run builds images — takes a few minutes)...${NC}"
docker compose up -d

echo ""
echo "╔══════════════════════════════════════════════════════════════════╗"
echo "║  All systems go!                                                 ║"
echo "╠══════════════════════════════════════════════════════════════════╣"
echo "║  Frontend  →  http://localhost:5173                              ║"
echo "║  Backend   →  http://localhost:8000                              ║"
echo "║  API docs  →  http://localhost:8000/docs                         ║"
echo "╠══════════════════════════════════════════════════════════════════╣"
echo "║  Login:  admin / admin123                                        ║"
echo "╠══════════════════════════════════════════════════════════════════╣"
echo "║  Logs:   docker compose logs -f                                  ║"
echo "║  Stop:   bash Installation/stop.sh                               ║"
echo "╚══════════════════════════════════════════════════════════════════╝"
