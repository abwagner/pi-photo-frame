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

- Change the default `admin` / `password` immediately after first setup.
- Keep dependencies updated (e.g. `pip install -U -r requirements.txt`).
- Run the app behind HTTPS in production when possible.
- Do not expose the app to the internet unless you need to; prefer local/VPN access.
