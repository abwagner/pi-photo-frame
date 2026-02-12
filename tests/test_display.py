"""Tests for display page, display token, display control, uploads serving, reorder, settings edge cases, 413, and auth edge cases."""

import json
import hashlib
import time
from unittest.mock import patch

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
import app as photo_app

from tests.conftest import make_test_image


# ===== Display Page =====

class TestDisplayPage:
    """Tests for /display access control."""

    def test_display_with_valid_token(self, client, app):
        """Display page with valid token returns 200."""
        token = photo_app.DISPLAY_TOKEN
        resp = client.get(f'/display?token={token}')
        assert resp.status_code == 200
        assert b'Photo Frame Display' in resp.data

    def test_display_without_token_or_session_redirects(self, client):
        """Display page without token or session from non-localhost redirects to login."""
        # Default test client uses 127.0.0.1 (localhost), so override to simulate external
        resp = client.get('/display', headers={'Host': 'example.com'},
                          environ_base={'REMOTE_ADDR': '192.168.1.100'})
        assert resp.status_code == 302
        assert '/login' in resp.headers['Location']

    def test_display_with_invalid_token_redirects(self, client):
        """Display page with bad token from non-localhost redirects to login."""
        resp = client.get('/display?token=bad-token', headers={'Host': 'example.com'},
                          environ_base={'REMOTE_ADDR': '192.168.1.100'})
        assert resp.status_code == 302
        assert '/login' in resp.headers['Location']

    def test_display_with_session(self, auth_client):
        """Display page with authenticated session returns 200."""
        resp = auth_client.get('/display')
        assert resp.status_code == 200

    def test_display_from_localhost(self, client, app):
        """Display page from localhost returns 200."""
        # The test client's REMOTE_ADDR is 127.0.0.1 by default
        resp = client.get('/display')
        # In test environment, remote_addr is 127.0.0.1, so this should work
        assert resp.status_code == 200


# ===== Display Token API =====

class TestDisplayToken:
    """Tests for /api/display-token."""

    def test_display_token_requires_admin(self, client):
        """GET /api/display-token without auth returns 401."""
        resp = client.get('/api/display-token')
        assert resp.status_code == 401

    def test_display_token_returns_token(self, auth_client):
        """GET /api/display-token returns the display token."""
        resp = auth_client.get('/api/display-token')
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'token' in data
        assert len(data['token']) > 0


# ===== Serving Uploads =====

class TestServeUploads:
    """Tests for /uploads/<filename>."""

    def test_serve_existing_upload(self, auth_client):
        """GET /uploads/<fname> returns the uploaded image."""
        buf = make_test_image(100, 100, 'red')
        resp = auth_client.post('/api/upload',
                                data={'files': (buf, 'test.png')},
                                content_type='multipart/form-data')
        fname = resp.get_json()['uploaded'][0]

        resp = auth_client.get(f'/uploads/{fname}')
        assert resp.status_code == 200
        assert resp.content_type.startswith('image/')

    def test_serve_nonexistent_upload(self, client):
        """GET /uploads/<bad_fname> returns 404."""
        resp = client.get('/uploads/nonexistent.png')
        assert resp.status_code == 404


# ===== Reorder API =====

class TestReorderAPI:
    """Tests for POST /api/reorder."""

    def test_reorder_images(self, auth_client):
        """POST /api/reorder persists image order."""
        order = ['b.png', 'a.png', 'c.png']
        resp = auth_client.post('/api/reorder',
                                json={'images': order},
                                content_type='application/json')
        assert resp.status_code == 200
        assert resp.get_json()['success'] is True

        settings = auth_client.get('/api/settings').get_json()
        assert settings['image_order'] == order

    def test_reorder_missing_images_field(self, auth_client):
        """POST /api/reorder without 'images' field returns 400."""
        resp = auth_client.post('/api/reorder',
                                json={},
                                content_type='application/json')
        assert resp.status_code == 400

    def test_reorder_requires_auth(self, client):
        """POST /api/reorder without auth returns 401."""
        resp = client.post('/api/reorder',
                           json={'images': []},
                           content_type='application/json')
        assert resp.status_code == 401


# ===== Settings Edge Cases =====

class TestSettingsEdgeCases:
    """Tests for settings API edge cases."""

    def test_get_settings_unauthenticated(self, client):
        """GET /api/settings works without authentication."""
        resp = client.get('/api/settings')
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'mat_color' in data

    def test_post_settings_unauthenticated(self, client):
        """POST /api/settings without auth returns 401."""
        resp = client.post('/api/settings',
                           json={'mat_color': '#000'},
                           content_type='application/json')
        assert resp.status_code == 401

    def test_post_settings_disallowed_field_ignored(self, auth_client):
        """POST /api/settings with disallowed fields ignores them."""
        auth_client.post('/api/settings',
                         json={'not_a_real_field': 'evil'},
                         content_type='application/json')
        settings = auth_client.get('/api/settings').get_json()
        assert 'not_a_real_field' not in settings


# ===== 413 Error Handler =====

class TestErrorHandler413:
    """Test for 413 Payload Too Large handler."""

    def test_413_returns_json(self, app):
        """413 error returns JSON with max size message."""
        with app.test_request_context():
            response, status = photo_app.too_large(None)
            assert status == 413
            data = response.get_json()
            assert 'error' in data
            assert '50MB' in data['error']


# ===== Auth Edge Cases =====

class TestAuthEdgeCases:
    """Tests for logout and legacy hash migration."""

    def test_logout_clears_session(self, client, app):
        """GET /logout clears session and redirects to login."""
        # Log in with a non-default password so forced change doesn't interfere
        photo_app.load_users()
        photo_app.change_user_password('admin', 'newpass123')
        client.post('/login', data={'username': 'admin', 'password': 'newpass123'})

        # Verify we're logged in (upload page returns 200)
        resp = client.get('/upload')
        assert resp.status_code == 200

        # Logout
        resp = client.get('/logout')
        assert resp.status_code == 302
        assert '/login' in resp.headers['Location']

        # Verify session is cleared
        resp = client.get('/upload')
        assert resp.status_code == 302
        assert '/login' in resp.headers['Location']

    def test_legacy_sha256_migration(self, app):
        """Login with legacy SHA-256 hash auto-migrates to bcrypt."""
        # Create a user with legacy SHA-256 hash
        password = 'testpass'
        salt = 'somesalt'
        legacy_hash = hashlib.sha256((salt + password).encode()).hexdigest()

        users = {
            'legacyuser': {
                'password_hash': legacy_hash,
                'salt': salt,
                'role': 'admin'
            }
        }
        photo_app.save_users(users)

        # Verify login works with legacy hash
        assert photo_app.verify_user('legacyuser', password) is True

        # Verify hash was migrated to bcrypt
        migrated_users = photo_app.load_users()
        assert migrated_users['legacyuser']['password_hash'].startswith('$2b$')
        assert migrated_users['legacyuser']['salt'] is None

    def test_verify_nonexistent_user(self, app):
        """verify_user returns False for nonexistent user."""
        photo_app.load_users()
        assert photo_app.verify_user('nobody', 'pass') is False


# ===== Display Control API =====

class TestDisplayControl:
    """Tests for /api/display/state and /api/display/control."""

    def _upload_images(self, auth_client, count=3):
        """Upload test images so slides exist."""
        for i in range(count):
            buf = make_test_image(100, 100, ['red', 'blue', 'green'][i % 3])
            auth_client.post('/api/upload',
                             data={'files': (buf, f'img{i}.png')},
                             content_type='multipart/form-data')

    def test_get_state_returns_structure(self, client, app):
        """GET /api/display/state returns index, paused, and total."""
        resp = client.get('/api/display/state')
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'index' in data
        assert 'paused' in data
        assert 'total' in data

    def test_get_state_no_auth_required(self, client, app):
        """GET /api/display/state works without auth."""
        resp = client.get('/api/display/state')
        assert resp.status_code == 200

    def test_control_requires_auth(self, client, app):
        """POST /api/display/control without auth returns 401."""
        resp = client.post('/api/display/control',
                           json={'action': 'next'},
                           content_type='application/json')
        assert resp.status_code == 401

    def test_control_invalid_action(self, auth_client):
        """POST /api/display/control with bad action returns 400."""
        resp = auth_client.post('/api/display/control',
                                json={'action': 'invalid'},
                                content_type='application/json')
        assert resp.status_code == 400

    def test_control_next(self, auth_client):
        """POST next advances the index."""
        self._upload_images(auth_client)
        # Reset state
        photo_app._display_state['index'] = 0
        photo_app._display_state['paused'] = True
        photo_app._display_state['last_advanced_at'] = time.time()

        resp = auth_client.post('/api/display/control',
                                json={'action': 'next'},
                                content_type='application/json')
        assert resp.status_code == 200
        assert resp.get_json()['index'] == 1

    def test_control_prev(self, auth_client):
        """POST prev decrements the index."""
        self._upload_images(auth_client)
        photo_app._display_state['index'] = 2
        photo_app._display_state['paused'] = True
        photo_app._display_state['last_advanced_at'] = time.time()

        resp = auth_client.post('/api/display/control',
                                json={'action': 'prev'},
                                content_type='application/json')
        assert resp.status_code == 200
        assert resp.get_json()['index'] == 1

    def test_control_pause_play(self, auth_client):
        """POST pause/play toggles paused state."""
        self._upload_images(auth_client)
        photo_app._display_state['index'] = 0
        photo_app._display_state['paused'] = False
        photo_app._display_state['last_advanced_at'] = time.time()

        resp = auth_client.post('/api/display/control',
                                json={'action': 'pause'},
                                content_type='application/json')
        assert resp.get_json()['paused'] is True

        resp = auth_client.post('/api/display/control',
                                json={'action': 'play'},
                                content_type='application/json')
        assert resp.get_json()['paused'] is False

    def test_auto_advance(self, auth_client):
        """After slideshow_interval seconds, index auto-advances."""
        self._upload_images(auth_client)
        photo_app._display_state['index'] = 0
        photo_app._display_state['paused'] = False
        # Set last_advanced_at to 15 seconds ago (interval is 10s default)
        photo_app._display_state['last_advanced_at'] = time.time() - 15

        resp = auth_client.get('/api/display/state')
        data = resp.get_json()
        assert data['index'] == 1  # Should have auto-advanced by 1

    def test_state_with_no_slides(self, client, app):
        """State returns index 0 when no slides exist."""
        resp = client.get('/api/display/state')
        data = resp.get_json()
        assert data['index'] == 0
        assert data['total'] == 0
