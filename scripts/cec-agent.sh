#!/usr/bin/env bash
# ============================================================
# Pi Photo Frame - CEC Agent
# ============================================================
#
# Runs on the display-only Pi. Registers this device's CEC
# capability with the backend, then polls for queued commands
# and executes them locally via cec-ctl.
#
# Usage: ./scripts/cec-agent.sh <backend-url> <display-token>
#
# Started automatically by start_kiosk.sh when CEC is enabled.
# Requires: cec-utils (apt install cec-utils)

set -euo pipefail

BACKEND_URL="${1:-}"
TOKEN="${2:-}"
POLL_INTERVAL=30   # seconds between polls
CEC_DEVICE="/dev/cec0"

if [[ -z "$BACKEND_URL" || -z "$TOKEN" ]]; then
    echo "[CEC] Usage: $0 <backend-url> <display-token>"
    exit 1
fi

# Strip trailing slash
BACKEND_URL="${BACKEND_URL%/}"

log() {
    echo "[CEC] $*"
    logger -t "pi-photo-frame-cec" "$*" 2>/dev/null || true
}

# Verify cec-ctl is installed and device is accessible
if ! command -v cec-ctl &>/dev/null; then
    log "cec-ctl not found. Install with: sudo apt install cec-utils"
    exit 1
fi

if [[ ! -e "$CEC_DEVICE" ]]; then
    log "No CEC device at $CEC_DEVICE. Exiting."
    exit 1
fi

if ! cec-ctl -d0 --phys-addr &>/dev/null 2>&1; then
    log "CEC device not responding. Exiting."
    exit 1
fi

log "CEC device found at $CEC_DEVICE."

# Register with backend — tells it a CEC-capable display is available
register() {
    local response
    response=$(curl -sf -X POST \
        -H "Content-Type: application/json" \
        -d "{\"token\": \"$TOKEN\"}" \
        --max-time 10 \
        "$BACKEND_URL/api/cec/register" 2>/dev/null) || true

    if echo "$response" | grep -q '"success": *true'; then
        log "Registered with backend."
        return 0
    fi
    log "Registration failed (will retry). Response: $response"
    return 1
}

# Fetch and dequeue the oldest pending command from the backend
fetch_pending() {
    curl -sf \
        --max-time 10 \
        "$BACKEND_URL/api/cec/pending?token=$TOKEN" 2>/dev/null || echo ""
}

# Execute a CEC command locally
run_cec() {
    local command="$1"
    case "$command" in
        on)
            log "Sending TV power ON."
            cec-ctl -d0 --playback --image-view-on || log "cec-ctl returned non-zero for 'on'."
            ;;
        standby)
            log "Sending TV standby."
            cec-ctl -d0 --playback --standby || log "cec-ctl returned non-zero for 'standby'."
            ;;
        *)
            log "Unknown command: $command"
            ;;
    esac
}

# Register on startup, retrying until the backend is reachable
log "Waiting for backend at $BACKEND_URL..."
for i in $(seq 1 40); do
    if curl -skf "$BACKEND_URL/login" &>/dev/null; then
        log "Backend is reachable."
        break
    fi
    sleep 5
done

register || true   # non-fatal if backend is temporarily unavailable

# Main polling loop
log "Polling for CEC commands every ${POLL_INTERVAL}s."
while true; do
    response=$(fetch_pending)

    if [[ -n "$response" ]]; then
        command=$(echo "$response" | python3 -c \
            "import sys, json; print(json.load(sys.stdin).get('command') or '')" 2>/dev/null || echo "")

        if [[ -n "$command" ]]; then
            run_cec "$command"
        fi
    fi

    # Re-register every ~10 minutes so the backend knows we're still alive
    # after a server restart (which resets _cec_display_has_cec)
    if (( SECONDS % 600 < POLL_INTERVAL )); then
        register || true
    fi

    sleep "$POLL_INTERVAL"
done
