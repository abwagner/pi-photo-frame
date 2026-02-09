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

info "Pulling latest changes..."
git fetch origin main
git reset --hard origin/main

info "Rebuilding and restarting containers..."
docker compose up -d --build

info "Deploy complete."
docker compose ps
