# OpenFotoFrame – Agent Overview

Web-based digital photo frame for Raspberry Pi or any Linux system. Users upload photos via a browser; the display runs a fullscreen slideshow on a connected TV or monitor.

## Tech Stack

- **Backend**: Flask (Python 3)
- **Frontend**: Vanilla JS, server-rendered Jinja2 templates
- **Deployment**: Docker + Caddy (HTTPS), optional Chromium kiosk

## Project Structure

```
off/
├── app.py              # Main Flask app: auth, uploads, gallery, groups, display API, backup
├── requirements.txt
├── Dockerfile
├── docker-compose.yml  # App + Caddy reverse proxy
├── Caddyfile           # HTTPS config (self-signed, Cloudflare, or DuckDNS)
├── data/               # Persisted: settings.json, users.json, gallery.json
├── uploads/            # Images + thumbnails/
├── templates/          # HTML (upload, gallery, display, login, admin)
├── scripts/            # install.sh, deploy.sh, cloudflare-ddns, restart-chromium
├── tests/              # Pytest tests
└── .github/workflows/  # CI/CD deploy
```

## Core Concepts

### Gallery

- Images live in `uploads/`; metadata in `data/gallery.json`.
- Each image has: `enabled`, `title`, `scale`, `mat_color`, `mat_finish`, `bevel_width`, `border_effect`, `crop`, `phash`, etc.
- Crop is normalized `{x, y, w, h}` (0–1) and stored per image.

### Groups

- Groups are multi-image slides displayed together.
- Group data in `gallery['groups']`: `images` (filenames), `scales` (per-image), `mat_color`, `mat_finish`, `bevel_width`, `border_effect`.
- Crop is per-image (in `gallery['images'][filename]['crop']`), not per-group.
- Slides: groups first, then ungrouped singles; optional shuffle with daily seed.

### Display

- `/display` fetches slides from `/api/images`.
- Each slide is single or group; supports crop, scale, mat, effects.
- Server-driven state: `/api/display/state`, `/api/display/control` for index and pause.

### Auth

- bcrypt passwords, session cookies, CSRF.
- Roles: admin (full access) and user (upload, gallery, own password).
- Display accessible via token or localhost, no login.

## Key API Endpoints

| Endpoint | Purpose |
|----------|---------|
| `GET /api/images` | Slides for display (single + group slides) |
| `GET /api/gallery` | All images + groups (management) |
| `PATCH /api/gallery/<filename>` | Update image metadata (scale, crop, mat, etc.) |
| `PATCH /api/groups/<id>` | Update group (mat, images, scales) |
| `POST /api/upload` | Upload images |
| `GET /api/settings` | Load settings |
| `POST /api/settings` | Save settings |

## Conventions

- Image metadata (including crop) is in `gallery['images'][filename]`.
- Thumbnails: 400px max, JPEG unless RGBA/LA/P (PNG) for transparency.
- Perceptual hash (pHash) for duplicate detection; Hamming distance < 10 triggers a warning.

## Deployment Modes

The backend and display can run on the same machine or on separate devices.

### All-in-one (default)
Backend (Flask + Caddy + Docker) and Chromium kiosk on the same Pi.
`install.sh` mode 1 sets this up; the kiosk reads the display token from Docker.

### Split: backend on any server, Pi as display only
```
Any machine                   Raspberry Pi (display only)
────────────────              ──────────────────────────
Docker (Flask + Caddy)  ←HTTP─  Chromium --kiosk
  port 443 (all hosts)          https://<backend>/display?token=TOKEN
```
`install.sh` mode 2 sets up the Pi side: installs Chromium, prompts for the
backend URL and display token, writes `start_kiosk.sh`, and adds an autostart
entry. No Docker is installed on the Pi.

**Getting the display token**: from the backend server, call
`GET /api/display-token` as an admin (or read `/app/data/.display_token` inside
the Docker container).

**Caddyfile**: uses `:443 { tls internal }` so it responds to any hostname —
both `localhost` connections from a local kiosk and LAN IP/domain connections
from a remote Pi. Chromium uses `--ignore-certificate-errors` for self-signed.

**Control API auth**: `/api/display/control` accepts the display token in the
JSON body (`{action, token}`) so a remote kiosk can use prev/next/pause buttons
without a login session.

## Testing

```bash
pytest
```
