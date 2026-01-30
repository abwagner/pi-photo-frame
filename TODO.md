# TODO — Public Release Preparation

Tracked items for preparing pi-photo-frame for a public GitHub repository.
Based on security review and [opensource.guide](https://opensource.guide/) recommendations.

---

## Before Making Public

- [x] **Add LICENSE file** — MIT License file added at root.
- [x] **Set `debug=False`** — `app.py` gates debug mode on `FLASK_DEBUG` env var (off by default).
- [ ] **Verify no secrets in git history** — Run a final check with [TruffleHog](https://github.com/trufflesecurity/trufflehog) or `git log -p --all -- "data/" "uploads/" ".secret_key" ".display_token"` before going public.

---

## Security — High Priority

- [x] **Upgrade password hashing** — Uses bcrypt via `bcrypt` package. Legacy SHA-256 hashes auto-migrate on login.
- [x] **Add CSRF protection** — Flask-WTF `CSRFProtect` enabled globally.
- [x] **Set session cookie flags** — `SESSION_COOKIE_HTTPONLY = True`, `SESSION_COOKIE_SAMESITE = 'Lax'`, and `SESSION_COOKIE_SECURE` gated on `SECURE_COOKIES` env var.
- [x] **Exclude secrets from Dropbox backup** — `rclone sync` excludes `.secret_key`, `.display_token`, and `users.json`.

---

## Security — Medium Priority

- [x] **Pin dependency versions** — `requirements.txt` uses exact pinned versions (`==`).
- [ ] **Enable Dependabot** — After publishing, enable Dependabot or Renovate for automatic security update PRs.
- [x] **Reverse proxy / `remote_addr`** — ProxyFix middleware enabled via `BEHIND_PROXY=1` env var.
- [x] **Harden `serve_upload`** — `serve_upload` validates filenames against gallery metadata before serving.
- [x] **XSS in template JS** — `upload.html` uses `escAttr()` helper to escape filenames in template literals.

---

## Open Source Guide Checklist

- [x] **LICENSE file** — MIT License present
- [x] **README.md** — Present and thorough
- [x] **CONTRIBUTING.md** — Present with dev setup, workflow, and style guidelines
- [x] **CODE_OF_CONDUCT.md** — Contributor Covenant adopted
- [x] **SECURITY.md** — Present (vulnerability reporting process)
- [x] **.gitignore** — Excludes `data/`, `uploads/`, secrets, Python artifacts
- [ ] **Branch protection on `main`** — Enable on GitHub: require PR reviews before merge
- [ ] **MFA for maintainers** — Enable on GitHub account
- [ ] **Private vulnerability reporting** — Enable in GitHub repo Security tab after publishing
- [x] **Issue / PR templates** — Added under `.github/`
