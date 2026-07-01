#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$SCRIPT_DIR")"

GREEN='\033[0;32m'; CYAN='\033[0;36m'; RED='\033[0;31m'; NC='\033[0m'
ok()   { echo -e "  ${GREEN}OK${NC}  $1"; }
fatal(){ echo -e "\n  ${RED}ERROR:${NC} $1"; exit 1; }

echo "╔══════════════════════════════════════════════════════════════════╗"
echo "║              DB Creator -- Setup & Start                        ║"
echo "╚══════════════════════════════════════════════════════════════════╝"

# 1. backend/.env
BACKEND_ENV="$ROOT/backend/.env"
if [ ! -f "$BACKEND_ENV" ]; then
  FERNET_KEY=$(python3 -c "import os,base64; print(base64.urlsafe_b64encode(os.urandom(32)).decode())" 2>/dev/null \
    || openssl rand -base64 32 | tr '+/' '-_' | tr -d '=\n')
  JWT_SECRET=$(python3 -c "import secrets; print(secrets.token_hex(32))" 2>/dev/null \
    || openssl rand -hex 32)
  ADMIN_KEY=$(python3 -c "import secrets; print(secrets.token_hex(16))" 2>/dev/null \
    || openssl rand -hex 16)
  ADMIN_PASS=$(python3 -c "import secrets; print(secrets.token_urlsafe(16))" 2>/dev/null \
    || openssl rand -base64 12)
  cat > "$BACKEND_ENV" <<EOF
DATABASE_URL=postgresql+asyncpg://dbcreator:dbcreator@localhost:5432/dbcreator
REDIS_URL=redis://localhost:6379/0
FERNET_KEY=${FERNET_KEY}
DEBUG=false
ENVIRONMENT=development
ADMIN_KEY=${ADMIN_KEY}
JWT_SECRET=${JWT_SECRET}
DEFAULT_ADMIN_PASSWORD=${ADMIN_PASS}
EOF
  ok "Created backend/.env with generated secrets"
  echo ""
  echo -e "  ${CYAN}Admin credentials (save these):${NC}"
  echo "    Username: admin"
  echo "    Password: ${ADMIN_PASS}"
  echo "    Admin key: ${ADMIN_KEY}"
  echo ""
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

# 4. Detect compose command (v2 plugin preferred, v1 standalone fallback)
if docker compose version &>/dev/null 2>&1; then
  DC="docker compose"
elif command -v docker-compose &>/dev/null; then
  DC="docker-compose"
else
  fatal "Neither 'docker compose' nor 'docker-compose' found. Install Docker Compose and re-run."
fi
ok "Compose: $DC"

# 5. Start
cd "$ROOT"
echo ""
echo -e "  ${CYAN}Starting all services (first run builds images -- takes a few minutes)...${NC}"
$DC up -d

echo ""
echo "╔══════════════════════════════════════════════════════════════════╗"
echo "║  All systems go!                                                 ║"
echo "╠══════════════════════════════════════════════════════════════════╣"
echo "║  Frontend  ->  http://localhost:5173                             ║"
echo "║  Backend   ->  http://localhost:8000                             ║"
echo "║  API docs  ->  http://localhost:8000/docs                        ║"
echo "╠══════════════════════════════════════════════════════════════════╣"
echo "║  Login:  admin / admin123                                        ║"
echo "╠══════════════════════════════════════════════════════════════════╣"
echo "║  Logs:   $DC logs -f"
echo "║  Stop:   bash Installation/stop.sh                               ║"
echo "╚══════════════════════════════════════════════════════════════════╝"
