"""MFA policy, TOTP, recovery, passkey, and reset tests."""

from types import SimpleNamespace
from unittest.mock import patch

import pyotp

import app as photo_app
from tests.conftest import TEST_ADMIN_PASSWORD


def _set_mfa_settings(**values):
    settings = photo_app.load_settings()
    settings.update(values)
    photo_app.save_settings(settings)


def _enroll_totp(auth_client):
    _set_mfa_settings(mfa_mode='optional', mfa_methods='either')
    started = auth_client.post('/api/mfa/totp/start').get_json()
    code = pyotp.TOTP(started['secret']).now()
    verified = auth_client.post('/api/mfa/totp/verify', json={'code': code})
    assert verified.status_code == 200
    return started, verified.get_json()['recovery_codes']


def test_mfa_defaults_disabled_for_backward_compatibility(auth_client):
    settings = photo_app.load_settings()
    assert settings['mfa_mode'] == 'disabled'
    auth_client.get('/logout')
    resp = auth_client.post('/login', data={'username': 'admin', 'password': TEST_ADMIN_PASSWORD})
    assert '/upload' in resp.headers['Location']


def test_required_admin_without_enrollment_is_sent_to_mfa(auth_client):
    _set_mfa_settings(mfa_mode='required_admins', mfa_methods='totp')
    auth_client.get('/logout')
    resp = auth_client.post('/login', data={'username': 'admin', 'password': TEST_ADMIN_PASSWORD})
    assert '/mfa' in resp.headers['Location']


def test_totp_enrollment_encrypts_secret_and_shows_recovery_once(auth_client):
    started, codes = _enroll_totp(auth_client)
    users = photo_app.load_users()
    mfa = users['admin']['mfa']
    assert started['secret'] not in mfa['totp_secret']
    assert photo_app._decrypt_mfa_secret(mfa['totp_secret']) == started['secret']
    assert len(codes) == 10
    serialized = photo_app.USERS_FILE.read_text()
    assert all(code not in serialized for code in codes)
    assert started['secret'] not in photo_app.SECURITY_LOG_FILE.read_text()


def test_recovery_code_is_one_time_second_factor(auth_client):
    _, codes = _enroll_totp(auth_client)
    auth_client.get('/logout')
    login = auth_client.post('/login', data={'username': 'admin', 'password': TEST_ADMIN_PASSWORD})
    assert '/mfa/challenge' in login.headers['Location']
    first = auth_client.post('/api/mfa/challenge/totp', json={'code': codes[0]})
    assert first.status_code == 200
    auth_client.get('/logout')
    auth_client.post('/login', data={'username': 'admin', 'password': TEST_ADMIN_PASSWORD})
    replay = auth_client.post('/api/mfa/challenge/totp', json={'code': codes[0]})
    assert replay.status_code == 401


def test_totp_timestep_cannot_be_reused(auth_client):
    started, _ = _enroll_totp(auth_client)
    auth_client.get('/logout')
    auth_client.post('/login', data={'username': 'admin', 'password': TEST_ADMIN_PASSWORD})
    replay = auth_client.post('/api/mfa/challenge/totp',
                              json={'code': pyotp.TOTP(started['secret']).now()})
    assert replay.status_code == 401


def test_security_settings_validation_and_audit(auth_client):
    bad = auth_client.post('/api/admin/security-settings', json={'mfa_mode': 'always-ish'})
    assert bad.status_code == 400
    good = auth_client.post('/api/admin/security-settings', json={
        'mfa_mode': 'required_all', 'mfa_methods': 'either',
        'webauthn_rp_id': 'frame.example', 'webauthn_origin': 'https://frame.example',
    })
    assert good.status_code == 200
    assert good.get_json()['passkeys_available'] is True
    assert 'security_settings_change' in photo_app.SECURITY_LOG_FILE.read_text()


def test_passkeys_gracefully_disabled_without_stable_https(auth_client):
    _set_mfa_settings(mfa_mode='optional', mfa_methods='passkey',
                      webauthn_rp_id='localhost', webauthn_origin='http://localhost')
    assert photo_app.passkeys_available() is False
    resp = auth_client.post('/api/mfa/passkeys/register/options')
    assert resp.status_code == 400


def test_passkey_registration_and_authentication(auth_client):
    _set_mfa_settings(mfa_mode='optional', mfa_methods='either',
                      webauthn_rp_id='frame.example', webauthn_origin='https://frame.example')
    options = auth_client.post('/api/mfa/passkeys/register/options')
    assert options.status_code == 200
    credential_id = b'credential-id'
    registered = SimpleNamespace(
        credential_id=credential_id, credential_public_key=b'public-key', sign_count=0,
    )
    credential_json = {'id': photo_app._b64url(credential_id), 'response': {}}
    with patch('app.verify_registration_response', return_value=registered):
        result = auth_client.post('/api/mfa/passkeys/register/verify', json={
            'name': 'Laptop', 'credential': credential_json,
        })
    assert result.status_code == 200
    passkey = photo_app.load_users()['admin']['mfa']['passkeys'][0]
    assert passkey['name'] == 'Laptop'

    auth_client.get('/logout')
    auth_client.post('/login', data={'username': 'admin', 'password': TEST_ADMIN_PASSWORD})
    assert auth_client.post('/api/mfa/passkeys/authenticate/options').status_code == 200
    authenticated = SimpleNamespace(new_sign_count=1)
    with patch('app.verify_authentication_response', return_value=authenticated):
        verified = auth_client.post('/api/mfa/passkeys/authenticate/verify',
                                    json={'credential': credential_json})
    assert verified.status_code == 200
    stored = photo_app.load_users()['admin']['mfa']['passkeys'][0]
    assert stored['sign_count'] == 1
    assert stored['last_used'] is not None


def test_admin_mfa_reset_is_csrf_protected_and_audited(auth_client, app):
    _enroll_totp(auth_client)
    app.config['WTF_CSRF_ENABLED'] = True
    rejected = auth_client.delete('/api/admin/users/admin/mfa')
    assert rejected.status_code == 400
    app.config['WTF_CSRF_ENABLED'] = False
    accepted = auth_client.delete('/api/admin/users/admin/mfa')
    assert accepted.status_code == 200
    assert 'mfa' not in photo_app.load_users()['admin']
    assert 'mfa_admin_reset' in photo_app.SECURITY_LOG_FILE.read_text()
