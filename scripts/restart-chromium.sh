#!/usr/bin/env bash
# Restart Chromium to prevent memory leaks.
# Called daily at 4:00 AM via cron. See scripts/install.sh for setup.

set -euo pipefail

LOG_TAG="chromium-restart"

log() {
    logger -t "$LOG_TAG" "$1"
}

log "Stopping Chromium processes..."
pkill -f chromium || true
sleep 2

# Relaunch kiosk if start_kiosk.sh exists
KIOSK_SCRIPT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/start_kiosk.sh"

if [ -x "$KIOSK_SCRIPT" ]; then
    log "Relaunching kiosk via $KIOSK_SCRIPT"
    export DISPLAY=:0
    nohup "$KIOSK_SCRIPT" > /dev/null 2>&1 &
else
    log "No start_kiosk.sh found, Chromium will not be relaunched"
fi

log "Done"
