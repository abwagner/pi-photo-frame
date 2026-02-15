"""Tests for TV schedule and CEC control API endpoints."""

import json
from unittest.mock import patch


def test_get_tv_schedules_requires_auth(client):
    """GET /api/tv-schedules without login is rejected."""
    resp = client.get('/api/tv-schedules')
    assert resp.status_code in (302, 401)


def test_get_tv_schedules_empty(auth_client):
    """GET /api/tv-schedules returns empty list by default."""
    resp = auth_client.get('/api/tv-schedules')
    data = resp.get_json()
    assert data['schedules'] == []


@patch('app.is_cec_available', return_value=False)
def test_cec_status_unavailable(mock_cec, auth_client):
    """CEC status reports unavailable when cec-ctl is missing."""
    resp = auth_client.get('/api/cec/status')
    assert resp.get_json()['available'] is False


@patch('app.is_cec_available', return_value=True)
def test_cec_status_available(mock_cec, auth_client):
    """CEC status reports available when cec-ctl works."""
    resp = auth_client.get('/api/cec/status')
    assert resp.get_json()['available'] is True


def test_save_tv_schedules(auth_client):
    """POST /api/tv-schedules saves and returns schedules."""
    schedules = [{
        'on_time': '07:00',
        'off_time': '22:00',
        'days': [0, 1, 2, 3, 4],
        'enabled': True
    }]
    resp = auth_client.post('/api/tv-schedules',
                            data=json.dumps({'schedules': schedules}),
                            content_type='application/json')
    data = resp.get_json()
    assert data['success'] is True
    assert len(data['schedules']) == 1
    assert 'id' in data['schedules'][0]


def test_save_tv_schedules_persists(auth_client):
    """Saved schedules persist via GET."""
    schedules = [{
        'on_time': '08:00',
        'off_time': '21:00',
        'days': [5, 6],
        'enabled': True
    }]
    auth_client.post('/api/tv-schedules',
                     data=json.dumps({'schedules': schedules}),
                     content_type='application/json')

    resp = auth_client.get('/api/tv-schedules')
    data = resp.get_json()
    assert len(data['schedules']) == 1
    assert data['schedules'][0]['on_time'] == '08:00'
    assert data['schedules'][0]['days'] == [5, 6]


def test_save_tv_schedules_invalid_time(auth_client):
    """Invalid time format returns 400."""
    schedules = [{'on_time': '25:00', 'off_time': '23:00', 'days': [0]}]
    resp = auth_client.post('/api/tv-schedules',
                            data=json.dumps({'schedules': schedules}),
                            content_type='application/json')
    assert resp.status_code == 400


def test_save_tv_schedules_invalid_days(auth_client):
    """Invalid days array returns 400."""
    schedules = [{'on_time': '07:00', 'off_time': '23:00', 'days': [8]}]
    resp = auth_client.post('/api/tv-schedules',
                            data=json.dumps({'schedules': schedules}),
                            content_type='application/json')
    assert resp.status_code == 400


def test_save_tv_schedules_multiple(auth_client):
    """Multiple schedules can be saved."""
    schedules = [
        {'on_time': '07:00', 'off_time': '23:00', 'days': [0, 1, 2, 3, 4], 'enabled': True},
        {'on_time': '09:00', 'off_time': '22:00', 'days': [5, 6], 'enabled': True}
    ]
    resp = auth_client.post('/api/tv-schedules',
                            data=json.dumps({'schedules': schedules}),
                            content_type='application/json')
    data = resp.get_json()
    assert data['success'] is True
    assert len(data['schedules']) == 2


@patch('app.cec_send_command', return_value={'success': True, 'error': None})
def test_cec_test_on(mock_cmd, auth_client):
    """Test CEC on command sends correctly."""
    resp = auth_client.post('/api/cec/test',
                            data=json.dumps({'command': 'on'}),
                            content_type='application/json')
    assert resp.get_json()['success'] is True
    mock_cmd.assert_called_once_with('on')


@patch('app.cec_send_command', return_value={'success': True, 'error': None})
def test_cec_test_standby(mock_cmd, auth_client):
    """Test CEC standby command sends correctly."""
    resp = auth_client.post('/api/cec/test',
                            data=json.dumps({'command': 'standby'}),
                            content_type='application/json')
    assert resp.get_json()['success'] is True
    mock_cmd.assert_called_once_with('standby')


def test_cec_test_invalid_command(auth_client):
    """CEC test with invalid command returns 400."""
    resp = auth_client.post('/api/cec/test',
                            data=json.dumps({'command': 'reboot'}),
                            content_type='application/json')
    assert resp.status_code == 400


# ===== cec-ctl integration unit tests =====

@patch('app.subprocess.run')
def test_is_cec_available_calls_cec_ctl(mock_run):
    """is_cec_available uses cec-ctl to probe the device."""
    from app import is_cec_available
    mock_run.return_value.returncode = 0
    assert is_cec_available() is True
    mock_run.assert_called_once_with(
        ['cec-ctl', '-d0', '--phys-addr'],
        capture_output=True, text=True, timeout=5
    )


@patch('app.subprocess.run')
def test_cec_send_command_on_calls_cec_ctl(mock_run):
    """cec_send_command('on') invokes cec-ctl with --image-view-on."""
    from app import cec_send_command
    mock_run.return_value.returncode = 0
    result = cec_send_command('on')
    assert result['success'] is True
    mock_run.assert_called_once_with(
        ['cec-ctl', '-d0', '--playback', '--image-view-on'],
        capture_output=True, text=True, timeout=10
    )


@patch('app.subprocess.run')
def test_cec_send_command_standby_calls_cec_ctl(mock_run):
    """cec_send_command('standby') invokes cec-ctl with --standby."""
    from app import cec_send_command
    mock_run.return_value.returncode = 0
    result = cec_send_command('standby')
    assert result['success'] is True
    mock_run.assert_called_once_with(
        ['cec-ctl', '-d0', '--playback', '--standby'],
        capture_output=True, text=True, timeout=10
    )


@patch('app.subprocess.run')
def test_cec_send_command_unknown(mock_run):
    """cec_send_command with unknown command returns error without calling subprocess."""
    from app import cec_send_command
    result = cec_send_command('reboot')
    assert result['success'] is False
    assert 'Unknown command' in result['error']
    mock_run.assert_not_called()
