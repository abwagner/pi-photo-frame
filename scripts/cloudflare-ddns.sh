#!/usr/bin/env bash
# ============================================================
# Cloudflare DDNS - Keeps DNS record in sync with dynamic IP
# ============================================================
#
# Usage: ./scripts/cloudflare-ddns.sh
#
# Reads DOMAIN, CLOUDFLARE_API_TOKEN, and CLOUDFLARE_ZONE_ID
# from the project's .env file. Creates the A record if it
# doesn't exist, updates it if the IP has changed.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$SCRIPT_DIR/../.env"

if [[ ! -f "$ENV_FILE" ]]; then
    echo "[DDNS] No .env file found"
    exit 1
fi

# Source .env
set -a
source "$ENV_FILE"
set +a

# Validate required vars
for var in DOMAIN CLOUDFLARE_API_TOKEN CLOUDFLARE_ZONE_ID; do
    if [[ -z "${!var:-}" ]]; then
        echo "[DDNS] Missing $var in .env"
        exit 1
    fi
done

API="https://api.cloudflare.com/client/v4"
AUTH="Authorization: Bearer $CLOUDFLARE_API_TOKEN"

# Helper: parse JSON with python3 (available on all Pi OS / Ubuntu)
json_val() {
    python3 -c "import sys,json; d=json.load(sys.stdin); print($1)"
}

# Get current public IP (try multiple services)
get_public_ip() {
    curl -sf --max-time 10 https://api.ipify.org \
        || curl -sf --max-time 10 https://ifconfig.me \
        || curl -sf --max-time 10 https://icanhazip.com
}

CURRENT_IP=$(get_public_ip | tr -d '[:space:]')
if [[ -z "$CURRENT_IP" ]]; then
    echo "[DDNS] Failed to get public IP"
    exit 1
fi

# Look up existing A record
RECORD_JSON=$(curl -sf -H "$AUTH" \
    "$API/zones/$CLOUDFLARE_ZONE_ID/dns_records?name=$DOMAIN&type=A")

RECORD_COUNT=$(echo "$RECORD_JSON" | json_val "d['result_info']['count']")

if [[ "$RECORD_COUNT" -eq 0 ]]; then
    # No record exists — create it
    echo "[DDNS] No A record for $DOMAIN, creating -> $CURRENT_IP"
    curl -sf -X POST -H "$AUTH" -H "Content-Type: application/json" \
        -d "{\"type\":\"A\",\"name\":\"$DOMAIN\",\"content\":\"$CURRENT_IP\",\"proxied\":false}" \
        "$API/zones/$CLOUDFLARE_ZONE_ID/dns_records" | json_val "'OK' if d['success'] else 'FAILED: '+str(d.get('errors'))"
else
    # Record exists — check if IP changed
    RECORD_ID=$(echo "$RECORD_JSON" | json_val "d['result'][0]['id']")
    RECORD_IP=$(echo "$RECORD_JSON" | json_val "d['result'][0]['content']")

    if [[ "$CURRENT_IP" == "$RECORD_IP" ]]; then
        echo "[DDNS] IP unchanged ($CURRENT_IP)"
        exit 0
    fi

    echo "[DDNS] IP changed: $RECORD_IP -> $CURRENT_IP"
    curl -sf -X PUT -H "$AUTH" -H "Content-Type: application/json" \
        -d "{\"type\":\"A\",\"name\":\"$DOMAIN\",\"content\":\"$CURRENT_IP\",\"proxied\":false}" \
        "$API/zones/$CLOUDFLARE_ZONE_ID/dns_records/$RECORD_ID" | json_val "'OK' if d['success'] else 'FAILED: '+str(d.get('errors'))"
fi
