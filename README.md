# 🖼️ Pi Photo Frame

A beautiful, web-based digital photo frame with user management, gallery controls, and HTTPS support. Runs on any Linux system — commonly deployed on a Raspberry Pi connected to a TV.

## Features

- **Web Upload Interface** - Upload photos from any device on your network
- **Multi-User Support** - Admin can create user accounts
- **Gallery Management** - Show/hide photos, bulk actions, delete
- **Password Protection** - Secure login with forced password change on first login
- **Duplicate Detection** - Perceptual hashing warns before uploading duplicate images
- **Individual Image Scale** - Adjust zoom per image or match heights across a group
- **Customizable Mat Colors** - 16 presets or any custom color, per-image overrides
- **Mat Finishes** - Flat, Linen, Suede, or Silk texture overlays
- **Inner Bevel** - Adjustable 45-degree V-groove cut effect around images (0-16px)
- **Smooth Slideshow** - Configurable timing and transitions
- **Drag & Drop Reordering** - Arrange photos in your preferred order
- **TV Power Schedule (HDMI-CEC)** - Automatically turn your TV on/off on a schedule
- **HTTPS** - Self-signed, Let's Encrypt via Cloudflare, or Let's Encrypt via DuckDNS
- **Kiosk Mode** - Auto-starts on boot for dedicated displays
- **Remote Access (Tailscale)** - Securely manage your frame from anywhere
- **CI/CD Deployment** - Automated updates via GitHub Actions with maintenance window

## Quick Start

```bash
git clone https://github.com/abwagner/pi-photo-frame.git
cd pi-photo-frame
./scripts/install.sh
```

The install script handles everything: Docker installation, building and starting the app with HTTPS, optional Chromium kiosk mode, and a daily Chromium restart cron job to prevent memory leaks.

After setup, access at `https://<your-ip>/upload`. If your system runs Avahi/mDNS (default on Raspberry Pi OS and most desktop Linux distros), you can also use `https://<your-hostname>.local/upload`.

## Setup (End-to-End)

### What You Need

- Any Linux machine (Raspberry Pi, Ubuntu server, etc.) with a desktop environment if using kiosk mode
- Network connection
- HDMI cable to a TV/monitor (if using as a dedicated display)

### Step 1: Install

```bash
ssh user@your-host
git clone https://github.com/abwagner/pi-photo-frame.git
cd pi-photo-frame
./scripts/install.sh
```

The script will:
1. Install Docker and enable it to start on boot
2. Ask which HTTPS mode you want (self-signed, Cloudflare, or DuckDNS)
3. Build and start the photo frame app with Caddy (HTTPS)
4. Ask if you want Chromium kiosk mode for a connected display
5. Ask if you want HDMI-CEC TV power control
6. Ask if you want Tailscale for secure remote access
7. Add a daily cron job (4:00 AM) to restart Chromium and prevent memory leaks

If you chose kiosk mode, reboot to start it:

```bash
sudo reboot
```

### Step 2: Upload Photos

From any device on your network (phone, laptop, etc.):

1. Open `https://<your-ip>/upload` (or `https://<your-domain>/upload` if using Let's Encrypt)
2. Log in with `admin` / `password`
3. You'll be prompted to set a new password before continuing
4. Upload photos — they appear on the display automatically

### Managing the Frame

These commands are run via SSH on the host machine:

| Task | Command |
|------|---------|
| View logs | `docker compose logs -f` |
| Restart | `docker compose restart` |
| Stop | `docker compose down` |
| Update code | `git pull && docker compose up -d --build` |
| Exit kiosk temporarily | Press `Ctrl+Alt+F1` to switch to terminal |
| Return to kiosk | Press `Ctrl+Alt+F7` to switch back to desktop |

### Headless Operation

Once kiosk mode is set up, you never need to touch the machine again. Everything is managed through the web interface from your phone or laptop. It just needs power and an HDMI connection to your display.

## Default Login

```
Username: admin
Password: password
```

On first login, you'll be redirected to a password change page. You must set a new password before accessing any other features. This prevents the default credentials from being left active.

## Pages

| Page | URL | Description |
|------|-----|-------------|
| Login | `/login` | Sign in |
| Upload | `/upload` | Upload photos, adjust settings |
| Gallery | `/gallery` | Manage photos (show/hide/delete) |
| Display | `/display` | Fullscreen slideshow for TV |
| Backup | `/backup` | Dropbox backup management (admin only) |
| Users | `/admin/users` | User management (admin only) |

## User Roles

| Role | Permissions |
|------|-------------|
| **Admin** | Upload, manage gallery, manage users, change settings, manage backup |
| **User** | Upload, manage gallery, change own password |

## Gallery Management

The gallery page lets you:

- **Show/Hide Photos** - Toggle visibility without deleting
- **Bulk Actions** - Select multiple photos to show/hide/delete
- **Filter View** - Show all, visible only, or hidden only
- **See Metadata** - Upload date, uploader, file size

Hidden photos remain on disk but won't appear in the slideshow.

## Settings

| Setting | Description |
|---------|-------------|
| **Mat Color** | Background color around photos (16 presets or custom) |
| **Mat Finish** | Texture overlay: Flat (default), Linen, Suede, or Silk |
| **Inner Bevel** | 45-degree V-groove cut width around images (0-16px) |
| **Slideshow Interval** | Seconds between transitions (3-300) |
| **Transition Duration** | Fade animation length |
| **Image Fit** | "Contain" (full image) or "Cover" (fill screen) |
| **Image Scale** | Individual zoom per image (0.1x-2.0x) |
| **Shuffle** | Randomize photo order |
| **Show Filename** | Display photo name on screen |
| **TV Power Schedule** | HDMI-CEC on/off times by day of week |

Mat color, mat finish, inner bevel, and image scale can be overridden per image or per group from the upload page preview.

## TV Power Schedule (HDMI-CEC)

Control your TV's power automatically using HDMI-CEC. During install, choose "Enable HDMI-CEC TV power control" to set up the CEC device passthrough.

### Configuring Schedules

In the web UI settings panel:
1. Click **+ Add Schedule** to create a new on/off time pair
2. Set the on time, off time, and select which days of the week
3. Add multiple schedules for different viewing patterns
4. Use **Test On** / **Test Off** buttons to verify CEC control works

### Requirements

- TV must support HDMI-CEC (most modern TVs do)
- Pi must be connected via HDMI
- `cec-utils` is installed automatically during setup
- The CEC device (`/dev/cec0`) must be passed through to the Docker container

### Troubleshooting CEC

- If CEC status shows "unavailable", ensure the device mapping is uncommented in `docker-compose.yml`
- Some TVs use different CEC brand names (Anynet+, Bravia Sync, SimpLink, etc.) — the protocol is the same
- Not all TVs respond to all CEC commands

## Duplicate Detection

When uploading photos, the app uses perceptual hashing (pHash) to detect potential duplicates:

- Each image gets a structural fingerprint that's compared against existing gallery images
- If a close match is found (Hamming distance < 10), you'll see a warning with a side-by-side comparison
- You can still choose to upload the image if desired
- Low-resolution images (below 1280x720) also trigger a warning

### Backfill Hashes

If you had photos uploaded before duplicate detection was added, run the backfill to compute hashes for existing images:

```
POST /api/gallery/backfill-hashes  (Admin only)
```

## Backup (Dropbox)

The app supports cloud backup of your photos and settings to Dropbox via [rclone](https://rclone.org/).

### Setup

1. Navigate to `/backup` (admin only)
2. Generate a Dropbox OAuth token and paste it into the configuration form
3. The app writes an rclone config and verifies the connection

### Features

- **Manual backup/restore** — Run a backup or restore from the `/backup` page
- **Scheduled backups** — Set a daily backup time (default: 3:00 AM)
- **Custom path** — Choose the Dropbox folder path for backups
- **History** — View past backup results on the `/backup` page
- **Disconnect** — Remove the Dropbox connection at any time

### Requirements

- `rclone` must be installed in the Docker container (included in the Dockerfile)
- A Dropbox account with an OAuth token

## Trusted HTTPS (Let's Encrypt)

By default, the app uses a self-signed certificate (works immediately but shows a browser warning). For a trusted certificate with no warnings, the install script offers two DNS challenge options:

### Option 1: Cloudflare DNS

Best if you already own a domain managed by Cloudflare.

1. During install, choose **Let's Encrypt via Cloudflare**
2. Enter your domain (e.g., `photos.example.com`)
3. Enter your Cloudflare API token
4. Enter your Cloudflare Zone ID (enables automatic DDNS updates)

**Getting a Cloudflare API token:**
1. Go to [Cloudflare API Tokens](https://dash.cloudflare.com/profile/api-tokens)
2. Click **Create Token** → use the **Edit zone DNS** template
3. Configure the token:
   - **Permissions**: Zone / DNS / Edit (pre-filled by the template)
   - **Zone Resources**: Include → Specific zone → select your domain
   - **Client IP Address Filtering**: Leave blank (optional — restrict which IPs can use the token)
   - **TTL**: Leave blank for no expiration, or set an end date if you prefer rotating tokens

**Zone ID** is on your domain's Cloudflare overview page (right sidebar, under "API").

If you provide the Zone ID, the install script sets up a DDNS cron job that runs every 6 hours. It checks your public IP and automatically creates or updates the A record in Cloudflare — no need to manually manage DNS when your IP changes. Caddy will automatically obtain and renew the certificate.

### Option 2: DuckDNS (Free)

Best if you don't own a domain. DuckDNS provides a free `yourname.duckdns.org` subdomain.

1. During install, choose **Let's Encrypt via DuckDNS**
2. Enter your DuckDNS subdomain (e.g., `myframe`)
3. Enter your DuckDNS token

**Getting a DuckDNS token:**
1. Go to [duckdns.org](https://www.duckdns.org) and sign in
2. Create a subdomain
3. Copy your token from the top of the page

### Switching Later

You can re-run `./scripts/install.sh` at any time to switch HTTPS modes. The script will update the Caddyfile and `.env` file, then rebuild the containers.

### Manual Configuration

If you prefer to configure manually instead of using the install script:
1. Copy `.env.example` to `.env` and fill in your values
2. The install script generates the appropriate `Caddyfile`, or you can edit it directly
3. Run `docker compose up -d --build` to apply changes

## Port Forwarding & LAN Access

If you're using Let's Encrypt with a domain (Cloudflare or DuckDNS), you'll need to configure your router so external traffic reaches the Pi.

### Port Forwarding

Forward these ports on your router to the Pi's local IP:

| Protocol | External Port | Internal Port | Destination |
|----------|--------------|---------------|-------------|
| TCP | 80 | 80 | Pi's local IP (e.g., `192.168.1.68`) |
| TCP | 443 | 443 | Pi's local IP |

The exact steps vary by router. Generally: log into your router's admin page, find **Port Forwarding** (sometimes under Firewall or NAT), and create rules for ports 80 and 443 pointing to the Pi.

### DHCP Reservation

Port forwarding rules target a specific local IP. If the Pi's IP changes (DHCP lease renewal), the rules break. Set up a **DHCP reservation** (also called a static lease) in your router to permanently assign the Pi's current IP to its MAC address. This is usually found near the DHCP settings in your router's admin page.

### Accessing from Inside Your LAN

The Pi itself accesses the frame via `localhost` (the kiosk uses this automatically). For other devices on your local network, some routers support **hairpin NAT** and the domain will work from inside the LAN too. If your router doesn't, you have a few options:

1. **By hostname** — If your system runs Avahi/mDNS (default on Raspberry Pi OS), use `https://<hostname>.local` (e.g., `https://raspberrypi.local`) from other devices on the LAN.

2. **Via Tailscale** — If Tailscale is installed, use the Tailscale IP (e.g., `https://100.x.x.x`) from any device on your Tailnet, regardless of network.

3. **By local IP** — Access `https://192.168.1.68` (your Pi's IP). This requires adding the IP to the Caddyfile's localhost block:

   ```
   localhost, 192.168.1.68 {
       tls internal
       reverse_proxy photo-frame:5000
   }
   ```

   Then restart Caddy: `docker compose restart caddy`. This uses a self-signed certificate (accept the browser warning once).

## Remote Access (Tailscale)

[Tailscale](https://tailscale.com) creates a secure mesh VPN so you can access your photo frame from anywhere without opening ports on your router.

### Setup

During install, choose "Install Tailscale for secure remote access". The script will:
1. Install Tailscale
2. Run `tailscale up` to authenticate with your Tailscale account
3. Display your Tailscale IP address

### Finding Your Tailscale IP

- During install, the IP is printed to the terminal
- In the web UI, the admin settings panel shows both local and Tailscale IPs (after changing the default password)
- On the Pi: `tailscale ip -4`

### Using with CI/CD

Set your `PI_HOST` secret to the Tailscale IP (e.g., `100.x.x.x`). The GitHub Actions runner needs Tailscale access to reach the Pi — either install Tailscale on the runner or use a Tailscale subnet router.

## CI/CD Deployment

Automated deployment via GitHub Actions. When you push to `main`, tests run and (if enabled) the update is deployed to your Pi.

### Setup

1. In your GitHub repository, go to **Settings > Secrets and variables > Actions**

2. Add these **secrets**:
   | Secret | Value |
   |--------|-------|
   | `PI_HOST` | Your Pi's IP (Tailscale IP recommended) |
   | `PI_USER` | SSH username (e.g., `pi`) |
   | `PI_SSH_KEY` | Private SSH key for the Pi |
   | `PI_SSH_PORT` | SSH port (optional, defaults to 22) |

3. Add this **variable**:
   | Variable | Value |
   |----------|-------|
   | `DEPLOY_ENABLED` | `true` |

### Maintenance Window

Deploys automatically check if the TV is currently scheduled to be on. If it is, the deploy is skipped to avoid interrupting the slideshow. The deploy will proceed on the next push when the TV is off.

This uses the `/api/maintenance-window` endpoint which checks TV schedules. If no schedules are configured, deploys always proceed.

### Manual Deploy

SSH into the Pi and run:

```bash
cd ~/pi-photo-frame
./scripts/deploy.sh
```

This also checks the maintenance window before proceeding.

## File Structure

```
pi-photo-frame/
├── app.py                  # Flask application
├── requirements.txt        # Python dependencies
├── Dockerfile              # Docker image definition
├── docker-compose.yml      # Docker Compose config (app + Caddy)
├── Caddyfile               # Caddy reverse proxy config (HTTPS)
├── .env.example            # HTTPS configuration template
├── caddy/
│   └── Dockerfile          # Custom Caddy build (DNS plugins)
├── scripts/
│   ├── install.sh          # One-command setup script
│   ├── deploy.sh           # Manual deploy script
│   ├── uninstall.sh        # Complete removal script
│   ├── cloudflare-ddns.sh  # DDNS updater (cron, every 6h)
│   └── restart-chromium.sh # Daily Chromium restart (cron)
├── .github/workflows/
│   └── deploy.yml          # CI/CD pipeline (test + deploy)
├── tests/                  # Test suite
├── uploads/                # Uploaded photos
├── data/                   # Settings, users, gallery data
│   ├── settings.json
│   ├── users.json
│   ├── gallery.json
│   └── .secret_key
└── templates/
    ├── login.html
    ├── upload.html
    ├── gallery.html
    ├── display.html
    ├── admin_users.html
    ├── backup.html
    ├── change_password.html
    └── error.html
```

## Security

- Passwords are hashed with bcrypt
- Session keys are randomly generated
- HTTPS via Caddy (self-signed, Cloudflare, or DuckDNS Let's Encrypt)
- Secure cookies enabled behind the reverse proxy
- Display page accessible via token or localhost
- Non-root user in Docker container

### Display Access

The display (`/display`) is accessible:
- From localhost (the machine itself)
- With a valid display token
- When logged in

This allows the display to show photos without login while protecting upload/management.

## API Endpoints

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/api/upload` | POST | User | Upload images |
| `/api/images` | GET | None | Get enabled images (for display) |
| `/api/gallery` | GET | User | Get all images with metadata |
| `/api/gallery/<file>` | PATCH | User | Update image metadata (scale, etc.) |
| `/api/gallery/<file>` | DELETE | User | Delete an image |
| `/api/gallery/bulk` | POST | User | Bulk enable/disable/delete |
| `/api/check-duplicates` | POST | User | Check files for duplicates before upload |
| `/api/gallery/backfill-hashes` | POST | Admin | Compute perceptual hashes for existing images |
| `/api/settings` | GET/POST | User (POST) | Get or update settings |
| `/api/tv-schedules` | GET/POST | User/Admin | Get or save TV power schedules |
| `/api/cec/status` | GET | User | Check if CEC is available |
| `/api/cec/test` | POST | Admin | Send test CEC command (on/standby) |
| `/api/network-info` | GET | Admin | Get local and Tailscale IP addresses |
| `/api/maintenance-window` | GET | None | Check if deploy is safe (TV off) |
| `/api/reorder` | POST | User | Reorder images |
| `/api/display-token` | GET | Admin | Get display access token |
| `/api/display/state` | GET | None | Get current slideshow state (index, paused) |
| `/api/display/control` | POST | User | Control slideshow (next, prev, pause, play) |
| `/api/groups` | GET/POST | User | List or create image groups |
| `/api/groups/<id>` | PATCH/DELETE | User | Update or delete an image group |
| `/api/backup/status` | GET | Admin | Get backup configuration status |
| `/api/backup/configure` | POST/DELETE | Admin | Connect or disconnect Dropbox |
| `/api/backup/run` | POST | Admin | Run a backup now |
| `/api/backup/restore` | POST | Admin | Restore from backup |
| `/api/backup/history` | GET | Admin | Get backup history |
| `/api/backup/settings` | POST | Admin | Update backup schedule/path |
| `/api/admin/users` | POST | Admin | Create user |
| `/api/admin/users/<user>` | DELETE | Admin | Delete user |
| `/api/admin/users/<user>/password` | POST | Admin | Reset password |

## Troubleshooting

### Forgot admin password?

Delete the users file to reset to default:

```bash
docker compose exec photo-frame rm /app/data/users.json
docker compose restart
```

### Photos not showing on display?

1. Check the gallery - photos might be hidden
2. Ensure at least one photo is set to "visible"
3. Check browser console for errors

### Can't access from other devices?

1. Ensure devices are on the same network
2. Use the server's IP address if `.local` hostname doesn't resolve
3. If using self-signed certificates, accept the browser warning
4. If using Let's Encrypt, ensure your DNS points to the Pi's IP

## Uninstall

To completely remove Pi Photo Frame (containers, images, volumes, cron jobs, and kiosk config):

```bash
cd ~/pi-photo-frame
./scripts/uninstall.sh
```

## License

MIT License - feel free to modify and share!
