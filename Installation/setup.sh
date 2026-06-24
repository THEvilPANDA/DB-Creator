#!/usr/bin/env bash
# DB Creator — setup + start script
# Works on Ubuntu (native) and Windows (via Git Bash)
# Run: bash Installation/setup.sh
set -euo pipefail

# ── Paths ──────────────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$SCRIPT_DIR")"
BACKEND="$ROOT/backend"
FRONTEND="$ROOT/frontend"
LOGS="$ROOT/logs"
VENV="$ROOT/.venv"

# ── Platform ───────────────────────────────────────────────────────────────────
case "$(uname -s)" in
  Linux*)                  PLATFORM="linux"   ;;
  CYGWIN*|MINGW*|MSYS*)   PLATFORM="windows" ;;
  Darwin*)                 PLATFORM="mac"     ;;
  *)                       PLATFORM="unknown" ;;
esac

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
info()    { echo -e "  ${GREEN}✓${NC} $1"; }
warn()    { echo -e "  ${YELLOW}!${NC} $1"; }
section() { echo ""; echo "── $1 "; }

echo "╔══════════════════════════════════════════════════════════════════╗"
echo "║              DB Creator — Setup & Start                         ║"
echo "╚══════════════════════════════════════════════════════════════════╝"
echo "  Platform: $PLATFORM  |  Root: $ROOT"

# ── 1. Prerequisites ───────────────────────────────────────────────────────────
section "Prerequisites"

install_linux_prereqs() {
  if ! command -v docker &>/dev/null; then
    warn "Installing Docker..."
    sudo apt-get update -qq
    sudo apt-get install -y docker.io docker-compose-plugin
    sudo systemctl enable --now docker
    # Add current user to docker group so they can run without sudo
    sudo usermod -aG docker "$USER"
    echo -e "\n${YELLOW}Docker installed. Please log out and back in, then re-run this script.${NC}"
    exit 0
  fi

  if ! command -v python3 &>/dev/null; then
    warn "Installing Python 3..."
    sudo apt-get install -y python3 python3-pip python3-venv
  fi

  if ! command -v node &>/dev/null; then
    warn "Installing Node.js..."
    sudo apt-get install -y nodejs npm
  fi
}

install_windows_prereqs() {
  if ! command -v docker &>/dev/null; then
    warn "Installing Docker Desktop via winget..."
    winget install Docker.DockerDesktop --silent --accept-source-agreements --accept-package-agreements
    echo -e "\n${YELLOW}Docker Desktop installed. Start it from the Start menu, then re-run this script.${NC}"
    exit 0
  fi

  if ! command -v python3 &>/dev/null && ! command -v python &>/dev/null; then
    warn "Installing Python via winget..."
    winget install Python.Python.3.11 --silent --accept-source-agreements --accept-package-agreements
  fi

  if ! command -v node &>/dev/null; then
    warn "Installing Node.js via winget..."
    winget install OpenJS.NodeJS.LTS --silent --accept-source-agreements --accept-package-agreements
  fi
}

[ "$PLATFORM" = "linux"   ] && install_linux_prereqs
[ "$PLATFORM" = "windows" ] && install_windows_prereqs

PYTHON=$(command -v python3 2>/dev/null || command -v python)
info "docker  $(docker --version | head -1)"
info "python  $($PYTHON --version 2>&1)"
info "node    $(node --version)"

# ── 2. .env ───────────────────────────────────────────────────────────────────
section ".env"
ENV_FILE="$BACKEND/.env"
if [ ! -f "$ENV_FILE" ]; then
  warn "Creating backend/.env with dev defaults..."
  cat > "$ENV_FILE" <<'ENVEOF'
DATABASE_URL=postgresql+asyncpg://dbcreator:dbcreator@localhost:5432/dbcreator
TEST_DATABASE_URL=postgresql+asyncpg://dbcreator:dbcreator@localhost:5432/dbcreator_test
REDIS_URL=redis://localhost:6379/0
FERNET_KEY=YnF46Ea_bY5OsdxJ2xOGoAo471HkEJslQfMpTxaRsNU=
DEBUG=false
ENVIRONMENT=development
ADMIN_KEY=dev-admin-key
JWT_SECRET=dev-jwt-secret-change-in-production
DEFAULT_ADMIN_PASSWORD=admin123
ENVEOF
  info "Created (edit before production use)"
else
  info ".env already exists"
fi

# ── 3. Docker services ────────────────────────────────────────────────────────
section "Docker services"

if ! docker info &>/dev/null; then
  if [ "$PLATFORM" = "linux" ]; then
    warn "Starting Docker daemon..."
    sudo systemctl start docker
    sleep 3
  else
    echo -e "${RED}Docker Desktop is not running. Start it, then re-run this script.${NC}"
    exit 1
  fi
fi

cd "$ROOT"
docker compose up -d postgres redis
info "Containers started"

echo -n "  Waiting for postgres"
for i in $(seq 1 30); do
  if docker exec dbcreator-postgres-1 pg_isready -U dbcreator &>/dev/null 2>&1; then
    echo ""
    info "Postgres ready"
    break
  fi
  echo -n "."
  sleep 1
  if [ "$i" -eq 30 ]; then
    echo ""
    echo -e "${RED}Postgres did not become ready in 30s. Check: docker logs dbcreator-postgres-1${NC}"
    exit 1
  fi
done

# ── 4. Python virtualenv + deps ───────────────────────────────────────────────
section "Python dependencies"

if [ ! -d "$VENV" ]; then
  warn "Creating virtual environment..."
  $PYTHON -m venv "$VENV"
fi

if [ "$PLATFORM" = "windows" ]; then
  VENV_PY="$VENV/Scripts/python"
  VENV_PIP="$VENV/Scripts/pip"
  VENV_ALEMBIC="$VENV/Scripts/alembic"
else
  VENV_PY="$VENV/bin/python"
  VENV_PIP="$VENV/bin/pip"
  VENV_ALEMBIC="$VENV/bin/alembic"
fi

"$VENV_PIP" install -r "$BACKEND/requirements.txt" --quiet
info "Packages installed"

# ── 5. Database migrations ────────────────────────────────────────────────────
section "Database migrations"
cd "$BACKEND"
"$VENV_ALEMBIC" upgrade head
info "Migrations up to date"

# ── 6. Node dependencies ──────────────────────────────────────────────────────
section "Node dependencies"
if [ ! -d "$FRONTEND/node_modules" ]; then
  warn "Running npm install (first time)..."
  npm --prefix "$FRONTEND" install
else
  info "node_modules already present"
fi

# ── 7. Start servers ──────────────────────────────────────────────────────────
section "Starting servers"
mkdir -p "$LOGS"

# Stop any processes already on these ports
if [ "$PLATFORM" = "linux" ]; then
  fuser -k 8000/tcp 2>/dev/null || true
  fuser -k 5173/tcp 2>/dev/null || true
fi

# Backend
nohup "$VENV_PY" -m uvicorn app.main:app \
  --host 0.0.0.0 --port 8000 --reload \
  --app-dir "$BACKEND" \
  > "$LOGS/backend.log" 2>&1 &
echo $! > "$ROOT/.backend.pid"
info "Backend started (PID $(cat "$ROOT/.backend.pid"))"

# Frontend
nohup npm --prefix "$FRONTEND" run dev \
  > "$LOGS/frontend.log" 2>&1 &
echo $! > "$ROOT/.frontend.pid"
info "Frontend started (PID $(cat "$ROOT/.frontend.pid"))"

# ── 8. Seed ───────────────────────────────────────────────────────────────────
section "Seeding database"
ADMIN_KEY_VAL=$(grep ^ADMIN_KEY "$ENV_FILE" | cut -d= -f2)
echo -n "  Waiting for API"
for i in $(seq 1 20); do
  if curl -s http://localhost:8000/health &>/dev/null 2>&1; then
    echo ""
    break
  fi
  echo -n "."
  sleep 1
done

SEED_RESULT=$(curl -s -X POST http://localhost:8000/api/v1/admin/seed \
  -H "X-Admin-Key: $ADMIN_KEY_VAL" \
  -H "Content-Type: application/json" 2>/dev/null || echo '{}')

if echo "$SEED_RESULT" | grep -q "templates_created"; then
  info "Database seeded"
else
  warn "Seed skipped or already done"
fi

# ── Done ──────────────────────────────────────────────────────────────────────
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
echo "║  Logs:   logs/backend.log                                        ║"
echo "║          logs/frontend.log                                       ║"
echo "╠══════════════════════════════════════════════════════════════════╣"
echo "║  Stop:   bash Installation/stop.sh                               ║"
echo "╚══════════════════════════════════════════════════════════════════╝"
