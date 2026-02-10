#!/usr/bin/env bash
# ============================================================
# Pi Photo Frame - One-Command Setup
# ============================================================
#
# Usage: ./scripts/install.sh
#
# What this script does:
#   1. Installs Docker and Docker Compose (if needed)
#   2. Enables Docker to start on boot
#   3. Builds and starts the photo frame + Caddy (HTTPS)
#   4. Optionally sets up Chromium kiosk mode for a connected display
#   5. Adds a daily cron job to restart Chromium (prevents memory leaks)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

info() { echo -e "${GREEN}[INFO]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }

# Detect the correct Chromium binary/package name for this distro
detect_chromium() {
    if command -v chromium-browser &>/dev/null; then
        echo "chromium-browser"
    elif command -v chromium &>/dev/null; then
        echo "chromium"
    else
        # Not installed yet — check which package is available
        if apt-cache show chromium-browser &>/dev/null 2>&1; then
            echo "chromium-browser"
        else
            echo "chromium"
        fi
    fi
}

# ---------- Docker ----------

install_docker() {
    if command -v docker &>/dev/null; then
        info "Docker already installed: $(docker --version)"
        return 0
    fi

    info "Installing Docker..."
    curl -fsSL https://get.docker.com | sh

    info "Adding $USER to the docker group..."
    sudo usermod -aG docker "$USER"

    warn "You were added to the docker group."
    warn "If this is a fresh install, you may need to log out and back in."
}

enable_docker_on_boot() {
    info "Enabling Docker to start on boot..."
    sudo systemctl enable docker
    sudo systemctl start docker
}

# Allow Docker containers to bind to privileged ports (80, 443)
allow_privileged_ports() {
    local sysctl_key="net.ipv4.ip_unprivileged_port_start"
    local current
    current=$(sysctl -n "$sysctl_key" 2>/dev/null || echo "1024")

    if [ "$current" -le 80 ]; then
        info "Privileged port binding already allowed (start=$current)"
        return 0
    fi

    info "Allowing containers to bind to ports 80/443..."
    echo "$sysctl_key=80" | sudo tee /etc/sysctl.d/allow-privileged-ports.conf > /dev/null
    sudo sysctl -p /etc/sysctl.d/allow-privileged-ports.conf > /dev/null
}

# ---------- HTTPS / TLS ----------

CONFIGURED_DOMAIN=""

setup_https() {
    echo ""
    echo "  HTTPS mode:"
    echo "    1) Self-signed certificate (default — works immediately, browser warning)"
    echo "    2) Let's Encrypt via Cloudflare (trusted cert, requires domain + API token)"
    echo "    3) Let's Encrypt via DuckDNS   (trusted cert, free subdomain)"
    echo ""
    read -rp "Choose HTTPS mode [1/2/3]: " https_mode

    case "$https_mode" in
        2) setup_letsencrypt_cloudflare ;;
        3) setup_letsencrypt_duckdns ;;
        *) info "Using self-signed certificates (default)." ;;
    esac
}

setup_letsencrypt_cloudflare() {
    echo ""
    read -rp "  Domain name (e.g. photos.example.com): " domain
    if [[ -z "$domain" ]]; then
        warn "No domain entered. Falling back to self-signed."
        return 0
    fi

    read -rp "  Cloudflare API token: " cf_token
    if [[ -z "$cf_token" ]]; then
        warn "No token entered. Falling back to self-signed."
        return 0
    fi

    # Write .env
    cat > "$PROJECT_DIR/.env" <<EOF
DOMAIN=$domain
CLOUDFLARE_API_TOKEN=$cf_token
EOF
    info "Saved Cloudflare credentials to .env"

    # Write Caddyfile for Let's Encrypt + localhost fallback
    cat > "$PROJECT_DIR/Caddyfile" <<EOF
$domain {
    tls {
        dns cloudflare {env.CLOUDFLARE_API_TOKEN}
    }
    reverse_proxy photo-frame:5000
}

localhost {
    tls internal
    reverse_proxy photo-frame:5000
}

http:// {
    redir https://{host}{uri} permanent
}
EOF
    info "Caddyfile configured for Let's Encrypt (Cloudflare DNS)."
    CONFIGURED_DOMAIN="$domain"
}

setup_letsencrypt_duckdns() {
    echo ""
    read -rp "  DuckDNS subdomain (e.g. myframe — becomes myframe.duckdns.org): " subdomain
    if [[ -z "$subdomain" ]]; then
        warn "No subdomain entered. Falling back to self-signed."
        return 0
    fi

    local domain="${subdomain}.duckdns.org"

    read -rp "  DuckDNS token: " duck_token
    if [[ -z "$duck_token" ]]; then
        warn "No token entered. Falling back to self-signed."
        return 0
    fi

    # Write .env
    cat > "$PROJECT_DIR/.env" <<EOF
DOMAIN=$domain
DUCKDNS_TOKEN=$duck_token
EOF
    info "Saved DuckDNS credentials to .env"

    # Write Caddyfile for Let's Encrypt + localhost fallback
    cat > "$PROJECT_DIR/Caddyfile" <<EOF
$domain {
    tls {
        dns duckdns {env.DUCKDNS_TOKEN}
    }
    reverse_proxy photo-frame:5000
}

localhost {
    tls internal
    reverse_proxy photo-frame:5000
}

http:// {
    redir https://{host}{uri} permanent
}
EOF
    info "Caddyfile configured for Let's Encrypt (DuckDNS)."
    CONFIGURED_DOMAIN="$domain"
}

# ---------- Build & start ----------

start_services() {
    info "Building and starting services (this may take a while on first run)..."
    cd "$PROJECT_DIR"
    docker compose up -d --build
    info "Services started."
}

# ---------- Kiosk mode (optional) ----------

setup_kiosk() {
    echo ""
    read -rp "Set up Chromium kiosk mode for a connected display? [y/N]: " kiosk_answer
    if [[ ! "$kiosk_answer" =~ ^[Yy]$ ]]; then
        info "Skipping kiosk setup."
        return 0
    fi

    local chromium_pkg
    chromium_pkg=$(detect_chromium)
    info "Using Chromium package: $chromium_pkg"

    info "Installing kiosk packages..."
    sudo apt-get update -qq
    sudo apt-get install -y -qq "$chromium_pkg" unclutter xdotool x11-xserver-utils

    # Re-detect after install to get the actual binary name
    local chromium_bin
    chromium_bin=$(detect_chromium)

    # Create kiosk start script
    info "Creating kiosk start script..."
    cat > "$PROJECT_DIR/start_kiosk.sh" <<KIOSKEOF
#!/bin/bash

CHROMIUM="$chromium_bin"

# Wait for the photo frame to be ready
echo "Waiting for server to start..."
for i in {1..60}; do
    if curl -sk https://localhost > /dev/null 2>&1; then
        echo "Server is ready!"
        break
    fi
    sleep 1
done

# Get the display token (if it exists)
DISPLAY_TOKEN_FILE="\$(dirname "\$0")/data/.display_token"
DISPLAY_URL="https://localhost/display"

if [ -f "\$DISPLAY_TOKEN_FILE" ]; then
    TOKEN=\$(cat "\$DISPLAY_TOKEN_FILE" 2>/dev/null)
    if [ -n "\$TOKEN" ]; then
        DISPLAY_URL="https://localhost/display?token=\$TOKEN"
    fi
fi

# Disable screen blanking/power management
xset s off
xset s noblank
xset -dpms

# Hide mouse cursor
unclutter -idle 0.5 -root &

# Start Chromium in kiosk mode
\$CHROMIUM \\
    --kiosk \\
    --noerrdialogs \\
    --disable-infobars \\
    --disable-session-crashed-bubble \\
    --disable-translate \\
    --no-first-run \\
    --start-fullscreen \\
    --autoplay-policy=no-user-gesture-required \\
    --check-for-update-interval=31536000 \\
    --ignore-certificate-errors \\
    "\$DISPLAY_URL"
KIOSKEOF
    chmod +x "$PROJECT_DIR/start_kiosk.sh"

    # Create autostart entry
    mkdir -p ~/.config/autostart
    cat > ~/.config/autostart/photo-frame-kiosk.desktop <<EOF
[Desktop Entry]
Type=Application
Name=Photo Frame Kiosk
Exec=$PROJECT_DIR/start_kiosk.sh
X-GNOME-Autostart-enabled=true
EOF

    info "Kiosk mode configured. It will launch automatically after reboot."
}

# ---------- Chromium restart cron ----------

setup_chromium_cron() {
    local cron_script="$PROJECT_DIR/scripts/restart-chromium.sh"
    local cron_entry="0 4 * * * $cron_script"

    if crontab -l 2>/dev/null | grep -qF "$cron_script"; then
        info "Chromium restart cron job already exists."
        return 0
    fi

    info "Adding daily Chromium restart cron job (4:00 AM)..."
    (crontab -l 2>/dev/null || true; echo "$cron_entry") | crontab -
    info "Cron job added."
}

# ---------- Main ----------

main() {
    echo ""
    echo "======================================"
    echo "  Pi Photo Frame - Setup"
    echo "======================================"
    echo ""

    install_docker
    enable_docker_on_boot
    allow_privileged_ports
    setup_https
    start_services
    setup_kiosk
    setup_chromium_cron

    local ip
    ip=$(hostname -I 2>/dev/null | awk '{print $1}')

    echo ""
    echo "======================================"
    info "Setup complete!"
    echo ""
    if [[ -n "$CONFIGURED_DOMAIN" ]]; then
        echo "  Upload photos at:"
        echo "    https://${CONFIGURED_DOMAIN}/upload"
        echo ""
        echo "  Display URL (for other screens):"
        echo "    https://${CONFIGURED_DOMAIN}/display"
        echo ""
        echo "  Trusted Let's Encrypt certificate — no browser warnings!"
        echo "  (Make sure your DNS points ${CONFIGURED_DOMAIN} to ${ip})"
    else
        echo "  Upload photos at:"
        echo "    https://${ip}/upload"
        echo ""
        echo "  Display URL (for other screens):"
        echo "    https://${ip}/display"
        echo ""
        echo "  (Self-signed certificate — browser will show a warning)"
        echo "  To switch to trusted certs later, run: ./scripts/install.sh"
    fi
    echo ""
    echo "  Default login:  admin / password"
    echo "  CHANGE THIS immediately after first login."
    echo ""
    echo "  Useful commands:"
    echo "    View logs:  docker compose logs -f"
    echo "    Restart:    docker compose restart"
    echo "    Rebuild:    docker compose up -d --build"
    echo ""
    echo "  Chromium restarts daily at 4:00 AM to prevent memory leaks."
    echo "======================================"
}

main "$@"
