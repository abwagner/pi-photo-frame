# Pi Photo Frame – Agent Overview

Web-based digital photo frame for Raspberry Pi or any Linux system. Users upload photos via a browser; the display runs a fullscreen slideshow on a connected TV or monitor.

## Tech Stack

- **Backend**: Flask (Python 3)
- **Frontend**: Vanilla JS, server-rendered Jinja2 templates
- **Deployment**: Docker + Caddy (HTTPS), optional Chromium kiosk

## Project Structure

```
pi-photo-frame/
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

## Testing

```bash
pytest
```
