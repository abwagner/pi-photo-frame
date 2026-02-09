"""Tests for forced password change, network info, and maintenance window."""

import json
from datetime import datetime
from unittest.mock import patch

import pytest

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
import app as photo_app


class TestForcedPasswordChange:
    """Tests for the forced password change on default credentials."""

    def test_login_with_default_password_redirects(self, client):
        """Login with default creds should redirect to change-password."""
        photo_app.load_users()
        resp = client.post('/login', data={
            'username': 'admin',
            'password': 'password'
        })
        assert resp.status_code == 302
        assert '/change-password' in resp.headers['Location']
        assert 'forced=1' in resp.headers['Location']

    def test_login_after_password_change_goes_to_upload(self, client):
        """After changing password, login should go to /upload."""
        photo_app.load_users()
        photo_app.change_user_password('admin', 'newpass123')

        resp = client.post('/login', data={
            'username': 'admin',
            'password': 'newpass123'
        })
        assert resp.status_code == 302
        assert '/upload' in resp.headers['Location']

    def test_forced_change_blocks_navigation(self, client):
        """With default password, accessing /upload should redirect to change-password."""
        photo_app.load_users()
        # Log in (will be redirected, but session is set)
        client.post('/login', data={
            'username': 'admin',
            'password': 'password'
        })
        # Try to access upload page
        resp = client.get('/upload')
        assert resp.status_code == 302
        assert '/change-password' in resp.headers['Location']

    def test_forced_change_skips_current_password(self, client):
        """Forced mode should not require current password field."""
        photo_app.load_users()
        client.post('/login', data={
            'username': 'admin',
            'password': 'password'
        })
        # Submit forced password change without current password
        resp = client.post('/change-password?forced=1', data={
            'forced': '1',
            'new_password': 'newpass123',
            'confirm': 'newpass123'
        })
        assert resp.status_code == 302
        assert '/upload' in resp.headers['Location']

        # Verify new password works
        assert photo_app.verify_user('admin', 'newpass123')

    def test_change_password_page_accessible_with_default(self, client):
        """Change password page should be accessible even with default password."""
        photo_app.load_users()
        client.post('/login', data={
            'username': 'admin',
            'password': 'password'
        })
        resp = client.get('/change-password?forced=1')
        assert resp.status_code == 200
        assert b'Set New Password' in resp.data
        assert b'Please set a new password' in resp.data

    def test_has_default_password_helper(self, app):
        """has_default_password should correctly detect default credentials."""
        photo_app.load_users()
        assert photo_app.has_default_password('admin') is True

        photo_app.change_user_password('admin', 'newpass123')
        assert photo_app.has_default_password('admin') is False

    def test_has_default_password_nonexistent_user(self, app):
        """has_default_password should return False for nonexistent users."""
        assert photo_app.has_default_password('nobody') is False


class TestNetworkInfo:
    """Tests for the /api/network-info endpoint."""

    def _get_auth_client_with_changed_password(self, client):
        """Get an authenticated client with a non-default password."""
        photo_app.load_users()
        photo_app.change_user_password('admin', 'newpass123')
        client.post('/login', data={
            'username': 'admin',
            'password': 'newpass123'
        })
        return client

    def test_network_info_requires_admin(self, client):
        """Non-authenticated users should get 401."""
        resp = client.get('/api/network-info')
        assert resp.status_code == 401

    def test_network_info_returns_data(self, client):
        """Admin should get network info with at least the expected keys."""
        client = self._get_auth_client_with_changed_password(client)
        with patch('app.subprocess.run') as mock_run:
            mock_run.side_effect = FileNotFoundError
            resp = client.get('/api/network-info')
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'local_ip' in data
        assert 'tailscale_ip' in data


class TestMaintenanceWindow:
    """Tests for the /api/maintenance-window endpoint."""

    def test_no_schedules_allows_deploy(self, client):
        """No TV schedules → can_deploy=True."""
        # Default settings have no schedules
        photo_app.load_settings()
        resp = client.get('/api/maintenance-window')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['can_deploy'] is True

    def test_during_tv_on_blocks_deploy(self, client, app):
        """During TV on-window → can_deploy=False."""
        # Set up a schedule that covers the current time
        now = datetime.now()
        on_time = f'{now.hour:02d}:00'
        off_time = f'{(now.hour + 1) % 24:02d}:00'
        # Only block if we're not at minute 0 of the off hour
        if now.minute == 0 and now.hour == (now.hour + 1) % 24:
            on_time = f'{now.hour:02d}:00'
            off_time = f'{(now.hour + 2) % 24:02d}:00'

        settings = photo_app.load_settings()
        settings['tv_schedules'] = [{
            'id': 'test1',
            'on_time': on_time,
            'off_time': off_time,
            'days': [now.weekday()],
            'enabled': True
        }]
        photo_app.save_settings(settings)

        resp = client.get('/api/maintenance-window')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['can_deploy'] is False
        assert 'TV is scheduled ON' in data['reason']

    def test_outside_schedule_allows_deploy(self, client, app):
        """Outside TV schedule → can_deploy=True."""
        now = datetime.now()
        # Set schedule for hours that don't include now
        past_hour = (now.hour - 3) % 24
        past_hour_end = (now.hour - 2) % 24

        settings = photo_app.load_settings()
        settings['tv_schedules'] = [{
            'id': 'test2',
            'on_time': f'{past_hour:02d}:00',
            'off_time': f'{past_hour_end:02d}:00',
            'days': [now.weekday()],
            'enabled': True
        }]
        photo_app.save_settings(settings)

        resp = client.get('/api/maintenance-window')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['can_deploy'] is True

    def test_disabled_schedule_allows_deploy(self, client, app):
        """Disabled schedules should not block deploys."""
        now = datetime.now()
        settings = photo_app.load_settings()
        settings['tv_schedules'] = [{
            'id': 'test3',
            'on_time': f'{now.hour:02d}:00',
            'off_time': f'{(now.hour + 1) % 24:02d}:00',
            'days': [now.weekday()],
            'enabled': False
        }]
        photo_app.save_settings(settings)

        resp = client.get('/api/maintenance-window')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['can_deploy'] is True

    def test_wrong_day_allows_deploy(self, client, app):
        """Schedule on a different day should not block deploys."""
        now = datetime.now()
        other_day = (now.weekday() + 1) % 7
        settings = photo_app.load_settings()
        settings['tv_schedules'] = [{
            'id': 'test4',
            'on_time': f'{now.hour:02d}:00',
            'off_time': f'{(now.hour + 1) % 24:02d}:00',
            'days': [other_day],
            'enabled': True
        }]
        photo_app.save_settings(settings)

        resp = client.get('/api/maintenance-window')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['can_deploy'] is True
