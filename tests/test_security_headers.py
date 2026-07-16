"""Browser security header and CSP regression tests."""

from pathlib import Path


def test_required_headers_and_enforced_csp(client):
    response = client.get('/login')
    assert response.headers['X-Content-Type-Options'] == 'nosniff'
    assert response.headers['Referrer-Policy'] == 'no-referrer'
    assert response.headers['X-Frame-Options'] == 'DENY'
    assert response.headers['Permissions-Policy'] == 'camera=(), microphone=(), geolocation=()'
    csp = response.headers['Content-Security-Policy']
    assert "default-src 'self'" in csp
    assert "script-src 'self'" in csp
    assert "script-src-attr 'none'" in csp
    assert "object-src 'none'" in csp
    assert "frame-ancestors 'none'" in csp
    assert "form-action 'self'" in csp
    assert "script-src 'self' 'unsafe-inline'" not in csp


def test_sensitive_responses_are_no_store(auth_client):
    for path in ('/login', '/change-password', '/mfa', '/api/settings',
                 '/api/display/state', '/api/admin/security-settings'):
        response = auth_client.get(path)
        assert response.headers['Cache-Control'] == 'no-store, private'


def test_hsts_only_for_explicit_trusted_https_hostname(client, app):
    original = (app.config['HSTS_ENABLED'], app.config['TRUSTED_HTTPS_HOSTNAME'])
    try:
        app.config['HSTS_ENABLED'] = True
        app.config['TRUSTED_HTTPS_HOSTNAME'] = 'frame.example'
        trusted = client.get('/login', base_url='https://frame.example')
        assert trusted.headers['Strict-Transport-Security'] == 'max-age=31536000'
        assert 'Strict-Transport-Security' not in client.get('/login', base_url='http://frame.example').headers
        assert 'Strict-Transport-Security' not in client.get('/login', base_url='https://localhost').headers
        assert 'Strict-Transport-Security' not in client.get('/login', base_url='https://192.0.2.10').headers
    finally:
        app.config['HSTS_ENABLED'], app.config['TRUSTED_HTTPS_HOSTNAME'] = original


def test_templates_use_external_script_and_style_blocks():
    template_dir = Path(__file__).parent.parent / 'templates'
    for template in template_dir.glob('*.html'):
        source = template.read_text()
        assert '<style>' not in source
        assert '<script>' not in source
        assert ' onclick=' not in source
        assert ' onchange=' not in source
        assert ' oninput=' not in source
