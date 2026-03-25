#!/usr/bin/env bash
# setup_test_env.sh — Deploy Nuclei Cloud test environment with vulnerable targets.
#
# Usage:
#   chmod +x scripts/setup_test_env.sh
#   ./scripts/setup_test_env.sh
#
# What it does:
#   1. Checks required dependencies (docker, compose, python3, psql client)
#   2. Creates .env from .env.example if missing
#   3. Builds and starts all services + test-profile targets
#   4. Waits for backend /health to return 200 (max 120 s)
#   5. Verifies target containers are reachable
#   6. Prints URLs and credentials
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

info()    { echo -e "${GREEN}[INFO]${NC}  $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error()   { echo -e "${RED}[ERROR]${NC} $*" >&2; }
die()     { error "$*"; exit 1; }

# ── 1. Dependency checks ──────────────────────────────────────────────────────
info "Checking dependencies..."

command -v docker   > /dev/null 2>&1 || die "docker not found — please install Docker"
command -v python3  > /dev/null 2>&1 || die "python3 not found"

# Detect compose command (v2 plugin vs standalone)
if docker compose version > /dev/null 2>&1; then
    COMPOSE="docker compose"
elif command -v docker-compose > /dev/null 2>&1; then
    COMPOSE="docker-compose"
else
    die "docker compose (v2) or docker-compose (v1) not found"
fi

if ! command -v psql > /dev/null 2>&1; then
    warn "psql not found — integration test DB verification will be skipped"
fi

info "Using compose command: $COMPOSE"

# ── 2. Create .env if missing ─────────────────────────────────────────────────
if [ ! -f .env ]; then
    if [ -f .env.example ]; then
        info "Creating .env from .env.example..."
        cp .env.example .env
        # Generate a random SECRET_KEY
        SECRET=$(python3 -c "import secrets; print(secrets.token_hex(32))")
        sed -i "s|SECRET_KEY=.*|SECRET_KEY=$SECRET|" .env
        info "Generated SECRET_KEY."
    else
        warn ".env.example not found — creating minimal .env"
        cat > .env <<EOF
SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
FIRST_ADMIN_EMAIL=admin@nucleicloud.local
FIRST_ADMIN_PASSWORD=changeme123!
POSTGRES_PASSWORD=nucleipass
FLOWER_USER=admin
FLOWER_PASSWORD=flowerpass
LOG_LEVEL=INFO
SCAN_TIMEOUT_SECONDS=3600
MAX_TARGETS_PER_SCAN=10000
MAX_FINDINGS_PER_SCAN=50000
EOF
    fi
fi

# Ensure SECRET_KEY is set (paranoia check)
# shellcheck source=/dev/null
source .env 2>/dev/null || true
if [ -z "${SECRET_KEY:-}" ]; then
    die "SECRET_KEY is not set in .env"
fi

# ── 3. Build and start all services ──────────────────────────────────────────
info "Building and starting services (including test targets)..."
$COMPOSE --profile test up -d --build

# ── 4. Wait for backend /health ───────────────────────────────────────────────
info "Waiting for backend /health endpoint (max 120 s)..."
MAX_WAIT=120
ELAPSED=0
BACKEND_URL="http://localhost/health"

# Check if nginx port 80 is exposed; fall back to direct backend port
if ! $COMPOSE port nginx 80 > /dev/null 2>&1; then
    BACKEND_URL="http://localhost:8000/health"
fi

until curl -sf "$BACKEND_URL" > /dev/null 2>&1; do
    if [ "$ELAPSED" -ge "$MAX_WAIT" ]; then
        error "Backend did not become healthy within ${MAX_WAIT}s."
        error "Check logs with: $COMPOSE logs backend"
        die "Setup failed."
    fi
    sleep 3
    ELAPSED=$((ELAPSED + 3))
    echo -n "."
done
echo ""

HEALTH=$(curl -sf "$BACKEND_URL" | python3 -c "import sys,json; d=json.load(sys.stdin); print(json.dumps(d, indent=2))" 2>/dev/null || echo "")
info "Backend health response:"
echo "$HEALTH"

# ── 5. Verify target containers are up ───────────────────────────────────────
info "Verifying target containers..."

check_target() {
    local name="$1"
    local url="$2"
    local max_wait=60
    local elapsed=0

    echo -n "  Waiting for $name at $url "
    until curl -sf "$url" > /dev/null 2>&1; do
        if [ "$elapsed" -ge "$max_wait" ]; then
            echo ""
            warn "$name did not become reachable within ${max_wait}s (non-fatal)"
            return 0
        fi
        sleep 3
        elapsed=$((elapsed + 3))
        echo -n "."
    done
    echo " OK"
}

# Resolve container IPs via docker network
DVWA_IP=$($COMPOSE port target-dvwa 80 2>/dev/null | cut -d: -f1 || echo "")
DVWA_PORT=$($COMPOSE port target-dvwa 80 2>/dev/null | cut -d: -f2 || echo "")

if [ -n "$DVWA_PORT" ] && [ "$DVWA_PORT" != "" ]; then
    check_target "DVWA"         "http://localhost:${DVWA_PORT}/"
fi

NGINX_PORT=$($COMPOSE port target-nginx-old 80 2>/dev/null | cut -d: -f2 || echo "")
if [ -n "$NGINX_PORT" ] && [ "$NGINX_PORT" != "" ]; then
    check_target "Nginx 1.14"   "http://localhost:${NGINX_PORT}/"
fi

JUICE_PORT=$($COMPOSE port target-juiceshop 3000 2>/dev/null | cut -d: -f2 || echo "")
if [ -n "$JUICE_PORT" ] && [ "$JUICE_PORT" != "" ]; then
    check_target "Juice Shop"   "http://localhost:${JUICE_PORT}/"
fi

# ── 6. Print summary ──────────────────────────────────────────────────────────
ADMIN_EMAIL="${FIRST_ADMIN_EMAIL:-admin@nucleicloud.local}"
ADMIN_PASS="${FIRST_ADMIN_PASSWORD:-changeme123!}"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
info "Setup complete!"
echo ""
echo "  Frontend:      http://localhost/"
echo "  API docs:      http://localhost/api/v1/docs"
echo "  Health check:  http://localhost/health"
echo "  Flower:        http://localhost/flower (admin:${FLOWER_PASSWORD:-flowerpass})"
echo ""
echo "  Admin login:   ${ADMIN_EMAIL} / ${ADMIN_PASS}"
echo ""
if [ -n "${DVWA_PORT:-}" ]; then
echo "  Target DVWA:       http://localhost:${DVWA_PORT}/"
fi
if [ -n "${NGINX_PORT:-}" ]; then
echo "  Target Nginx 1.14: http://localhost:${NGINX_PORT}/"
fi
if [ -n "${JUICE_PORT:-}" ]; then
echo "  Target JuiceShop:  http://localhost:${JUICE_PORT}/"
fi
echo ""
echo "  Run unit tests:"
echo "    $COMPOSE exec backend pytest tests/unit/ -v"
echo ""
echo "  Run integration tests:"
echo "    python3 tests/integration/test_integration.py"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
