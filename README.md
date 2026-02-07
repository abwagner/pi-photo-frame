# 🖼️ Pi Photo Frame

A beautiful, web-based digital photo frame with user management, gallery controls, and HTTPS support. Runs on any Linux system — commonly deployed on a Raspberry Pi connected to a TV.

## Features

- **Web Upload Interface** - Upload photos from any device on your network
- **Multi-User Support** - Admin can create user accounts
- **Gallery Management** - Show/hide photos, bulk actions, delete
- **Password Protection** - Secure login for upload and management
- **Customizable Mat Colors** - Choose from presets or any custom color
- **Smooth Slideshow** - Configurable timing and transitions
- **Drag & Drop Reordering** - Arrange photos in your preferred order
- **HTTPS** - Self-signed TLS via Caddy reverse proxy
- **Kiosk Mode** - Auto-starts on boot for dedicated displays

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
2. Build and start the photo frame app with Caddy (HTTPS)
3. Ask if you want Chromium kiosk mode for a connected display
4. Add a daily cron job (4:00 AM) to restart Chromium and prevent memory leaks

If you chose kiosk mode, reboot to start it:

```bash
sudo reboot
```

### Step 2: Upload Photos

From any device on your network (phone, laptop, etc.):

1. Open `https://<your-ip>/upload` in a browser (accept the self-signed certificate warning)
2. Log in with `admin` / `password`
3. **Change the default password** (Admin > Users)
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

⚠️ **Change this password immediately after first login!**

## Pages

| Page | URL | Description |
|------|-----|-------------|
| Login | `/login` | Sign in |
| Upload | `/upload` | Upload photos, adjust settings |
| Gallery | `/gallery` | Manage photos (show/hide/delete) |
| Display | `/display` | Fullscreen slideshow for TV |
| Users | `/admin/users` | User management (admin only) |

## User Roles

| Role | Permissions |
|------|-------------|
| **Admin** | Upload, manage gallery, manage users, change settings |
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
| **Mat Color** | Background color around photos |
| **Slideshow Interval** | Seconds between transitions (3-300) |
| **Transition Duration** | Fade animation length |
| **Image Fit** | "Contain" (full image) or "Cover" (fill screen) |
| **Shuffle** | Randomize photo order |
| **Show Filename** | Display photo name on screen |

## File Structure

```
pi-photo-frame/
├── app.py                  # Flask application
├── requirements.txt        # Python dependencies
├── Dockerfile              # Docker image definition
├── docker-compose.yml      # Docker Compose config (app + Caddy)
├── Caddyfile               # Caddy reverse proxy config (HTTPS)
├── scripts/
│   ├── install.sh          # One-command setup script
│   ├── uninstall.sh        # Complete removal script
│   └── restart-chromium.sh # Daily Chromium restart (cron)
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
    ├── change_password.html
    └── error.html
```

## Security

- Passwords are hashed with bcrypt
- Session keys are randomly generated
- HTTPS via Caddy with self-signed certificate
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
| `/api/gallery/<file>` | PATCH | User | Update image metadata |
| `/api/gallery/<file>` | DELETE | User | Delete an image |
| `/api/gallery/bulk` | POST | User | Bulk enable/disable/delete |
| `/api/settings` | GET/POST | User (POST) | Get or update settings |
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
3. Accept the self-signed certificate warning in your browser

## Uninstall

To completely remove Pi Photo Frame (containers, images, volumes, cron jobs, and kiosk config):

```bash
cd ~/pi-photo-frame
./scripts/uninstall.sh
```

## License

MIT License - feel free to modify and share!
