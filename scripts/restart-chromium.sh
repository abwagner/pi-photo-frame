#!/usr/bin/env bash
# Restart Chromium to prevent memory leaks.
# Called daily at 4:00 AM via cron. See scripts/install.sh for setup.

set -euo pipefail

LOG_TAG="chromium-restart"

log() {
    logger -t "$LOG_TAG" "$1"
}

log "Stopping Chromium processes..."
# Kill Chromium only (not the start_kiosk.sh loop).
# The loop in start_kiosk.sh will automatically restart Chromium
# with a fresh process after a brief pause.
pkill -f 'chromium.*--kiosk' || true
sleep 2

log "Done (kiosk loop will auto-restart Chromium)"
