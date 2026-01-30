# Security Review for Public GitHub Release

This document summarizes a security review of pi-photo-frame in anticipation of publishing to a public GitHub repo, aligned with [Open Source Guides](https://opensource.guide/) (including [Security Best Practices](https://opensource.guide/security-best-practices-for-your-project/) and [Starting a Project](https://opensource.guide/starting-a-project/)).

---

## Fixes Applied in This Review

| Item | Action |
|------|--------|
| **Secrets in repo** | Added **`.gitignore`** so `data/`, `uploads/`, `.secret_key`, `.display_token`, and common dev artifacts are never committed. |
| **Vulnerability reporting** | Added **`SECURITY.md`** describing how to report vulnerabilities privately (required for trust and coordinated disclosure). |
| **Display token file** | **`.display_token`** is now restricted to owner-only (0o600) on create and on startup, matching `.secret_key`. |

---

## Critical: Do Before Making the Repo Public

1. **Add a LICENSE file**
   Your README says "MIT License" but there is no `LICENSE` file. Without it, the project is not clearly open source. Copy the [MIT license](https://choosealicense.com/licenses/mit/) into a root `LICENSE` file.

2. **Confirm no secrets in history**
   Run a quick check (e.g. `git log -p --all -- "data/" "uploads/" ".secret_key" ".display_token" "*.json"`) and use [GitHub’s secret scanning](https://docs.github.com/en/code-security/secret-scanning) or a tool like [Trufflehog](https://github.com/trufflesecurity/trufflehog) before making the repo public. If anything sensitive was ever committed, use `git filter-repo` or similar and rotate any exposed secrets.

3. **Turn off debug in production**
   In `app.py`, `app.run(..., debug=True)` is on. For any production or exposed deployment, use `debug=False` or run via a WSGI server (e.g. Gunicorn) with debug disabled.

---

## High Priority Recommendations

### Authentication and secrets

- **Password hashing**
  Passwords use salted SHA-256. For new code, prefer a dedicated password hashing library (e.g. **bcrypt**, **argon2**) for slow, memory-hard hashing. You can keep current hashes and migrate on next password change or force reset.

- **Session cookies**
  Set secure flags for production (HTTPS):
  `SESSION_COOKIE_SECURE = True`, `SESSION_COOKIE_HTTPONLY = True`, `SESSION_COOKIE_SAMESITE = 'Lax'` (or `'Strict'` if you don’t need cross-site POSTs).

### CSRF

- **Forms and state-changing APIs**
  There is no CSRF protection. For browser-originated POSTs (login, change password, create user, upload, backup config, etc.), add CSRF tokens (e.g. Flask-WTF or a custom token checked on POST) to reduce risk of cross-site request forgery.

### Unauthenticated endpoints

- **`GET /api/settings`**
  Returns all settings (e.g. mat color, intervals) with no auth. This is used by the display page; if you want to lock it down, you could either require the display token for a “public” settings payload or keep it read-only and low sensitivity.

- **`GET /api/images`**
  Unauthenticated; used by the display. Acceptable if you’re fine with anyone who can reach the server seeing the list of enabled image filenames/slides.

### Backup and sensitive data

- **Dropbox backup**
  `rclone sync` of `DATA_FOLDER` currently backs up `.secret_key`, `users.json`, and other data. Only `rclone/**` and `.backup.lock` are excluded. If the Dropbox account is compromised, session secret and password hashes are exposed. Consider excluding `.secret_key` and `users.json` from backup (or backing them up only via a separate, encrypted mechanism).

---

## Medium / Lower Priority

- **Dependencies**
  Pin versions in `requirements.txt` (e.g. `flask==3.x.x`) and enable Dependabot (or Renovate) so you get PRs for known vulnerabilities. Keep Werkzeug at a patched version (e.g. ≥3.0.6 for CVE-2024-49766; 3.1.4+ if you care about Windows device-name handling).

- **Path handling**
  `serve_upload` uses `send_from_directory` with the URL filename. Werkzeug’s `safe_join` limits path traversal; for defense in depth you could allow-list filenames that exist in your gallery/uploads.

- **Reverse proxy and `remote_addr`**
  Display access allows “localhost” via `request.remote_addr`. If you put the app behind a reverse proxy, ensure the proxy sets (and the app trusts) something like `X-Forwarded-For` only from the proxy, and that “localhost” is not spoofable from the internet.

- **Production run**
  Use a WSGI server (e.g. Gunicorn) and HTTPS in front of the app instead of `flask run` and `debug=True`.

---

## Open Source Guide Checklist (from opensource.guide)

| Item | Status |
|------|--------|
| **LICENSE** (e.g. MIT) | ❌ Add `LICENSE` file |
| **README** | ✅ Present |
| **CONTRIBUTING** | ⚠️ Optional but recommended |
| **CODE_OF_CONDUCT** | ⚠️ Optional but recommended (e.g. Contributor Covenant) |
| **SECURITY.md** (reporting + optional incident response) | ✅ Added |
| No secrets in repo / history | ⚠️ Verify; `.gitignore` added |
| Branch protection (main) | ⚠️ Enable on GitHub: require PR + review before merge |
| MFA for maintainers | ⚠️ Enable on GitHub |
| Dependabot / Renovate | ⚠️ Enable for dependency alerts |
| Private vulnerability reporting (GitHub) | ⚠️ Enable in repo Security tab |

---

## Summary

- **Done:** `.gitignore`, `SECURITY.md`, and `.display_token` file permissions.
- **Before going public:** Add `LICENSE`, verify no secrets in history, and disable debug in production.
- **Next steps:** Stronger password hashing, session cookie flags, CSRF, backup exclusions for secrets, dependency pinning and automation.

This should put you in good shape for a responsible public release and aligns with opensource.guide security and project-setup practices.
