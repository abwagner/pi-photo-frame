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
