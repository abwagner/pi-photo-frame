"""Tests for Backup API: status, configure, run, restore, disconnect, history, settings."""

import json
from unittest.mock import patch, MagicMock

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
import app as photo_app


def _get_admin_client(client):
    """Get an authenticated admin client with a non-default password."""
    photo_app.load_users()
    photo_app.change_user_password('admin', 'newpass123')
    client.post('/login', data={'username': 'admin', 'password': 'newpass123'})
    return client


class TestBackupStatus:
    """Tests for GET /api/backup/status."""

    def test_status_requires_admin(self, client):
        """GET /api/backup/status without auth returns 401."""
        resp = client.get('/api/backup/status')
        assert resp.status_code == 401

    def test_status_when_not_configured(self, client):
        """Status shows configured=False when rclone not set up."""
        client = _get_admin_client(client)
        resp = client.get('/api/backup/status')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['configured'] is False
        assert 'backup_time' in data
        assert 'backup_path' in data

    def test_status_when_configured(self, client, app):
        """Status shows configured=True when rclone config exists."""
        client = _get_admin_client(client)
        # Write a fake rclone config
        rclone_config = photo_app.RCLONE_CONFIG_FILE
        rclone_config.parent.mkdir(parents=True, exist_ok=True)
        rclone_config.write_text('[dropbox]\ntype = dropbox\ntoken = {"access_token":"fake"}')

        resp = client.get('/api/backup/status')
        data = resp.get_json()
        assert data['configured'] is True


class TestBackupConfigure:
    """Tests for POST/DELETE /api/backup/configure."""

    def test_configure_no_token(self, client):
        """POST /api/backup/configure with empty token returns 400."""
        client = _get_admin_client(client)
        resp = client.post('/api/backup/configure',
                           json={'token': ''},
                           content_type='application/json')
        assert resp.status_code == 400
        assert 'No token' in resp.get_json()['error']

    def test_configure_invalid_json_token(self, client):
        """POST /api/backup/configure with non-JSON token returns 400."""
        client = _get_admin_client(client)
        resp = client.post('/api/backup/configure',
                           json={'token': 'not-json'},
                           content_type='application/json')
        assert resp.status_code == 400
        assert 'Invalid token' in resp.get_json()['error']

    def test_configure_rclone_not_installed(self, client, app):
        """POST /api/backup/configure when rclone missing returns 500."""
        client = _get_admin_client(client)
        token = '{"access_token":"fake","token_type":"bearer"}'
        with patch('app.subprocess.run', side_effect=FileNotFoundError):
            resp = client.post('/api/backup/configure',
                               json={'token': token},
                               content_type='application/json')
        assert resp.status_code == 500
        assert 'rclone is not installed' in resp.get_json()['error']

    def test_configure_success(self, client, app):
        """POST /api/backup/configure with valid token and working rclone succeeds."""
        client = _get_admin_client(client)
        token = '{"access_token":"fake","token_type":"bearer"}'
        mock_result = MagicMock()
        mock_result.returncode = 0
        with patch('app.subprocess.run', return_value=mock_result):
            resp = client.post('/api/backup/configure',
                               json={'token': token},
                               content_type='application/json')
        assert resp.status_code == 200
        assert resp.get_json()['success'] is True

    def test_configure_rclone_test_fails(self, client, app):
        """POST /api/backup/configure when rclone test fails returns 400."""
        client = _get_admin_client(client)
        token = '{"access_token":"fake","token_type":"bearer"}'
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = 'auth failed'
        with patch('app.subprocess.run', return_value=mock_result):
            resp = client.post('/api/backup/configure',
                               json={'token': token},
                               content_type='application/json')
        assert resp.status_code == 400
        assert 'Connection test failed' in resp.get_json()['error']

    def test_disconnect(self, client, app):
        """DELETE /api/backup/configure removes rclone config."""
        client = _get_admin_client(client)
        # Set up a fake config first
        rclone_config = photo_app.RCLONE_CONFIG_FILE
        rclone_config.parent.mkdir(parents=True, exist_ok=True)
        rclone_config.write_text('[dropbox]\ntype = dropbox\n')

        resp = client.delete('/api/backup/configure')
        assert resp.status_code == 200
        assert not rclone_config.exists()


class TestBackupRun:
    """Tests for POST /api/backup/run and /api/backup/restore."""

    def test_run_not_configured(self, client):
        """POST /api/backup/run when not configured returns 400."""
        client = _get_admin_client(client)
        resp = client.post('/api/backup/run')
        assert resp.status_code == 400
        assert 'not configured' in resp.get_json()['error']

    def test_restore_not_configured(self, client):
        """POST /api/backup/restore when not configured returns 400."""
        client = _get_admin_client(client)
        resp = client.post('/api/backup/restore')
        assert resp.status_code == 400
        assert 'not configured' in resp.get_json()['error']


class TestBackupHistory:
    """Tests for GET /api/backup/history."""

    def test_history_empty(self, client):
        """GET /api/backup/history returns empty history when no backups."""
        client = _get_admin_client(client)
        resp = client.get('/api/backup/history')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['history'] == []

    def test_history_requires_admin(self, client):
        """GET /api/backup/history without auth returns 401."""
        resp = client.get('/api/backup/history')
        assert resp.status_code == 401


class TestBackupSettings:
    """Tests for POST /api/backup/settings."""

    def test_update_backup_time(self, client):
        """POST /api/backup/settings updates backup_time."""
        client = _get_admin_client(client)
        resp = client.post('/api/backup/settings',
                           json={'backup_time': '04:30'},
                           content_type='application/json')
        assert resp.status_code == 200

        status = client.get('/api/backup/status').get_json()
        assert status['backup_time'] == '04:30'

    def test_update_backup_time_invalid(self, client):
        """POST /api/backup/settings with bad time returns 400."""
        client = _get_admin_client(client)
        resp = client.post('/api/backup/settings',
                           json={'backup_time': '25:00'},
                           content_type='application/json')
        assert resp.status_code == 400

    def test_update_backup_path(self, client):
        """POST /api/backup/settings updates backup_path."""
        client = _get_admin_client(client)
        resp = client.post('/api/backup/settings',
                           json={'backup_path': 'my-custom-path'},
                           content_type='application/json')
        assert resp.status_code == 200

        status = client.get('/api/backup/status').get_json()
        assert status['backup_path'] == 'my-custom-path'
