# Contributing to Pi Photo Frame

Thanks for your interest in contributing! Here's how to get started.

## Development Setup

1. **Clone the repo**
   ```bash
   git clone https://github.com/<your-username>/pi-photo-frame.git
   cd pi-photo-frame
   ```

2. **Create a virtual environment**
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

3. **Run the development server**
   ```bash
   FLASK_DEBUG=1 python app.py
   ```
   The app will be available at `http://localhost:5000`. Default login: `admin` / `password`.

4. **Or use Docker**
   ```bash
   docker compose up --build
   ```

## Project Structure

- `app.py` — Flask application (routes, API, backup, auth)
- `templates/` — Jinja2 HTML templates
- `requirements.txt` — Pinned Python dependencies
- `Dockerfile` / `docker-compose.yml` — Container setup

## Submitting Changes

1. Fork the repository and create a feature branch from `main`.
2. Make your changes. Keep commits focused and descriptive.
3. Test locally (both browser UI and the Docker build if applicable).
4. Open a pull request against `main` with a clear description of the change.

## Reporting Bugs

Open an issue with:
- Steps to reproduce
- Expected vs. actual behavior
- Browser / OS / deployment method (Docker, bare metal Pi, etc.)

## Security Issues

**Do not open public issues for security vulnerabilities.** See [SECURITY.md](SECURITY.md) for reporting instructions.

## Code Style

- Python: follow existing conventions in `app.py` (standard library imports first, then third-party, then local).
- Templates: keep inline `<script>` and `<style>` blocks consistent with the existing structure.
- No new runtime dependencies without discussion in an issue first.

## License

By contributing, you agree that your contributions will be licensed under the [MIT License](LICENSE).
