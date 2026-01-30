# 🖼️ Pi Photo Frame

A beautiful, web-based digital photo frame for Raspberry Pi with user management, gallery controls, and Docker support.

## Features

- **Web Upload Interface** - Upload photos from any device on your network
- **Multi-User Support** - Admin can create user accounts
- **Gallery Management** - Show/hide photos, bulk actions, delete
- **Password Protection** - Secure login for upload and management
- **Customizable Mat Colors** - Choose from presets or any custom color
- **Smooth Slideshow** - Configurable timing and transitions
- **Drag & Drop Reordering** - Arrange photos in your preferred order
- **Docker Support** - Easy containerized deployment
- **Kiosk Mode** - Auto-starts on boot for dedicated displays

## Quick Start

### Option 1: Docker (Recommended)

```bash
cd pi-photo-frame
docker compose up -d
```

Access at `http://localhost:5000`

See [DOCKER.md](DOCKER.md) for detailed Docker instructions.

### Option 2: Direct Python

```bash
cd pi-photo-frame
pip install -r requirements.txt
python app.py
```

### Option 3: Raspberry Pi Kiosk

```bash
cd pi-photo-frame
chmod +x setup_kiosk.sh
./setup_kiosk.sh
sudo reboot
```

## Raspberry Pi Setup (End-to-End)

This walks through everything from a fresh Raspberry Pi to a working photo frame on your TV.

### What You Need

- Raspberry Pi (3B+ or newer recommended) with Raspberry Pi OS (Desktop version)
- microSD card (16GB+) with Raspberry Pi OS flashed via [Raspberry Pi Imager](https://www.raspberrypi.com/software/)
- HDMI cable connecting the Pi to your TV
- Network connection (Wi-Fi or Ethernet)

### Step 1: Initial Pi Setup

If you haven't already, flash Raspberry Pi OS with Desktop using [Raspberry Pi Imager](https://www.raspberrypi.com/software/). During setup in the imager, configure:
- Hostname (e.g. `photoframe`)
- Wi-Fi credentials
- Enable SSH (so you can manage it headlessly later)
- Set username/password

Boot the Pi and ensure it's connected to your network.

### Step 2: Get the Code onto the Pi

**Option A: Clone from GitHub (on the Pi)**

```bash
ssh pi@photoframe.local    # or whatever hostname/IP you set
git clone https://github.com/YOUR_USER/pi-photo-frame.git
cd pi-photo-frame
```

**Option B: Copy from your computer**

```bash
# From your Mac/PC:
scp -r pi-photo-frame pi@photoframe.local:~/
```

### Step 3: Install and Run

Choose **one** of these approaches:

#### Docker (Recommended)

Docker handles all dependencies in an isolated container and auto-restarts on boot.

```bash
# Install Docker on the Pi
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
# Log out and back in for group change to take effect
exit
ssh pi@photoframe.local

# Start the photo frame
cd ~/pi-photo-frame
docker compose up -d
```

The app is now running at `http://photoframe.local:5001` (port 5001 as configured in docker-compose.yml).

#### Native Python (Alternative)

Runs directly without Docker. The `setup_kiosk.sh` script handles everything:

```bash
cd ~/pi-photo-frame
chmod +x setup_kiosk.sh
./setup_kiosk.sh
```

This installs dependencies, creates a systemd service (auto-starts on boot), and configures kiosk mode. The app runs at `http://photoframe.local:5000`.

### Step 4: Set Up Kiosk Mode (Auto-Display on TV)

This makes the Pi automatically open the slideshow fullscreen in Chromium when it boots.

**If using Docker**, create the kiosk scripts manually:

```bash
# Install kiosk dependencies
sudo apt-get install -y chromium-browser unclutter

# Create autostart directory
mkdir -p ~/.config/autostart

# Create kiosk start script
cat > ~/start-kiosk.sh << 'EOF'
#!/bin/bash
# Wait for Docker and the server to be ready
echo "Waiting for photo frame server..."
for i in {1..60}; do
    if curl -s http://localhost:5001 > /dev/null 2>&1; then
        echo "Server is ready!"
        break
    fi
    sleep 2
done

# Disable screen blanking
xset s off
xset s noblank
xset -dpms

# Hide cursor
unclutter -idle 0.5 -root &

# Open Chromium in kiosk mode
chromium-browser \
    --kiosk \
    --noerrdialogs \
    --disable-infobars \
    --disable-session-crashed-bubble \
    --no-first-run \
    --start-fullscreen \
    http://localhost:5001/display
EOF
chmod +x ~/start-kiosk.sh

# Create autostart entry
cat > ~/.config/autostart/photo-frame-kiosk.desktop << 'EOF'
[Desktop Entry]
Type=Application
Name=Photo Frame Kiosk
Exec=/home/pi/start-kiosk.sh
X-GNOME-Autostart-enabled=true
EOF
```

**If using native Python**, the `setup_kiosk.sh` script already configured this.

Reboot to start kiosk mode:

```bash
sudo reboot
```

### Step 5: Upload Photos

From any device on your network (phone, laptop, etc.):

1. Open `http://photoframe.local:5001/upload` in a browser
2. Log in with `admin` / `password`
3. **Change the default password** (Admin > Users)
4. Upload photos — they appear on the TV automatically

### Managing the Frame

| Task | Command (SSH into Pi) |
|------|----------------------|
| View logs | `docker compose logs -f` |
| Restart | `docker compose restart` |
| Stop | `docker compose down` |
| Update code | `git pull && docker compose build && docker compose up -d` |
| Exit kiosk temporarily | Press `Ctrl+Alt+F1` to switch to terminal |
| Return to kiosk | Press `Ctrl+Alt+F7` to switch back to desktop |

### Headless Operation

Once kiosk mode is set up, you never need to touch the Pi again. Everything is managed through the web interface from your phone or laptop. The Pi just needs power and an HDMI connection to your TV.

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
├── docker-compose.yml      # Docker Compose config
├── DOCKER.md               # Docker deployment guide
├── setup_kiosk.sh          # Raspberry Pi kiosk setup
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

- Passwords are salted and hashed (SHA-256)
- Session keys are randomly generated
- Display page accessible via token or localhost
- Non-root user in Docker container

### Display Access

The TV display (`/display`) is accessible:
- From localhost (the Pi itself)
- With a valid display token
- When logged in

This allows the TV to show photos without login while protecting upload/management.

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
# Docker
docker compose exec photo-frame rm /app/data/users.json
docker compose restart

# Native
rm data/users.json
# Restart the app
```

### Photos not showing on display?

1. Check the gallery - photos might be hidden
2. Ensure at least one photo is set to "visible"
3. Check browser console for errors

### Can't access from other devices?

1. Check firewall allows port 5000
2. Use the server's IP address, not `localhost`
3. Ensure devices are on the same network

## License

MIT License - feel free to modify and share!
