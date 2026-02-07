#!/usr/bin/env bash
# ============================================================
# Pi Photo Frame - Uninstall
# ============================================================
#
# Usage: ./scripts/uninstall.sh
#
# Removes containers, images, volumes, cron jobs, and kiosk config.
# Optionally deletes the project directory.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

info()  { echo -e "${GREEN}[INFO]${NC} $1"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; }

echo ""
echo "======================================"
echo "  Pi Photo Frame - Uninstall"
echo "======================================"
echo ""
warn "This will stop and remove all containers, images, and volumes."
warn "All uploaded photos and data will be permanently deleted."
echo ""
read -rp "Are you sure? [y/N]: " confirm
if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
    info "Cancelled."
    exit 0
fi

# Stop and remove containers, images, and volumes
info "Stopping and removing containers, images, and volumes..."
cd "$PROJECT_DIR"
docker compose down --rmi all --volumes 2>/dev/null || true

# Remove Chromium restart cron job
if crontab -l 2>/dev/null | grep -qF "restart-chromium.sh"; then
    info "Removing Chromium restart cron job..."
    crontab -l 2>/dev/null | grep -v "restart-chromium.sh" | crontab -
fi

# Remove kiosk autostart
if [ -f ~/.config/autostart/photo-frame-kiosk.desktop ]; then
    info "Removing kiosk autostart entry..."
    rm -f ~/.config/autostart/photo-frame-kiosk.desktop
fi

# Remove generated start_kiosk.sh
if [ -f "$PROJECT_DIR/start_kiosk.sh" ]; then
    info "Removing generated start_kiosk.sh..."
    rm -f "$PROJECT_DIR/start_kiosk.sh"
fi

# Optionally remove the project directory
echo ""
read -rp "Delete the project directory ($PROJECT_DIR)? [y/N]: " delete_dir
if [[ "$delete_dir" =~ ^[Yy]$ ]]; then
    info "Deleting $PROJECT_DIR..."
    cd ~
    rm -rf "$PROJECT_DIR"
fi

echo ""
info "Uninstall complete."
