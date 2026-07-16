# Security Policy

## Supported Versions

We release security updates for the current release branch. Older branches are not officially supported.

## Reporting a Vulnerability

**Please do not report security vulnerabilities in public issues or pull requests.**

If you believe you've found a security issue:

1. **Email** the maintainers or open a [private security advisory](https://docs.github.com/en/code-security/security-advisories/working-with-security-advisories/creating-a-private-security-advisory) on GitHub (recommended once the repo is public).
2. Include a clear description, steps to reproduce, and impact if possible.
3. We will acknowledge receipt and aim to respond within a reasonable time.
4. We will work on a fix and coordinate disclosure (e.g. release + advisory) before any public discussion.

We appreciate responsible disclosure and will credit reporters when we publish advisories (unless you prefer to stay anonymous).

## Security Practices

- Consume the random one-time administrator password locally and change it on first login.
- Keep dependencies updated (e.g. `pip install -U -r requirements.txt`).
- Run the app behind HTTPS in production when possible.
- Do not expose the app to the internet unless you need to; prefer local/VPN access.

## Display enrollment and proxy trust

Display enrollment secrets are accepted only by `POST /api/display/enroll`. Never
put the secret in a URL, kiosk command, service argument, or proxy configuration.
After enrollment the browser uses an expiring HttpOnly, SameSite session cookie.
Rotating the enrollment secret immediately invalidates every existing display session.

Set `BEHIND_PROXY=1` only when the application is reachable exclusively through a
trusted reverse proxy that overwrites forwarded headers. When Flask is directly
exposed, leave it disabled so client-supplied forwarded addresses are ignored.

The display-side CEC scheduling agent has a separate `CEC_AGENT_TOKEN`; display
enrollment credentials and browser sessions cannot register an agent or dequeue
commands. Store the agent token in a mode-`0600` file and send it only in the
`Authorization: Bearer` header. Never place it in JSON, query strings, service
arguments, or logs.

All password creation, change, and reset paths require at least 12 characters.
Structured security events are stored in the protected data volume and contain a
timestamp, event type, username when known, source IP, and outcome. They must never
contain passwords, MFA/recovery secrets, display or CEC credentials, cookies, or
CSRF values.

MFA is configurable as disabled, optional, required for administrators, or required
for all users. Deployments may allow TOTP, passkeys, or either. Passkeys require a
stable trusted HTTPS origin whose hostname exactly matches the configured relying-
party ID. TOTP secrets are encrypted at rest using the mode-`0600` `.mfa_key`; only
hashes of one-time recovery codes are stored.

Browser security headers and CSP are emitted by Flask so they remain active without
Caddy. HSTS remains disabled unless explicitly enabled for an exact trusted HTTPS
hostname; it is never emitted for HTTP, localhost, raw IP, or mismatched hosts.
