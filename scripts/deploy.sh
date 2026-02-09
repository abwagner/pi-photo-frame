#!/usr/bin/env bash
# ============================================================
# Pi Photo Frame - Manual Deploy
# ============================================================
# Usage: ./scripts/deploy.sh
# Pulls latest code from main and rebuilds containers.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

GREEN='\033[0;32m'
NC='\033[0m'
info() { echo -e "${GREEN}[INFO]${NC} $1"; }

cd "$PROJECT_DIR"

# Check maintenance window (skip deploy if TV is on)
info "Checking maintenance window..."
MW_RESPONSE=$(curl -sf http://localhost:5000/api/maintenance-window 2>/dev/null || echo '{"can_deploy":true,"reason":"App not reachable"}')
CAN_DEPLOY=$(echo "$MW_RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin).get('can_deploy', True))" 2>/dev/null || echo "True")
MW_REASON=$(echo "$MW_RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin).get('reason', ''))" 2>/dev/null || echo "")

if [ "$CAN_DEPLOY" = "False" ]; then
    info "Deploy blocked: $MW_REASON"
    info "Skipping deploy. Will retry on next trigger."
    exit 0
fi

info "Pulling latest changes..."
git fetch origin main
git reset --hard origin/main

info "Rebuilding and restarting containers..."
docker compose up -d --build

info "Deploy complete."
docker compose ps
