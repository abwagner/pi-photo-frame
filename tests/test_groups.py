"""Tests for Groups API: create, list, update, delete, and display slides."""

import json

from tests.conftest import make_test_image


def _upload_images(auth_client, count=2):
    """Upload multiple images and return their filenames."""
    filenames = []
    for i in range(count):
        buf = make_test_image(100 + i * 10, 100 + i * 10, ['red', 'blue', 'green'][i % 3])
        resp = auth_client.post('/api/upload',
                                data={'files': (buf, f'img{i}.png')},
                                content_type='multipart/form-data')
        filenames.append(resp.get_json()['uploaded'][0])
    return filenames


def test_create_group(auth_client):
    """POST /api/groups with 2+ images creates a group."""
    fnames = _upload_images(auth_client, 2)
    resp = auth_client.post('/api/groups',
                            json={'images': fnames},
                            content_type='application/json')
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['success'] is True
    assert 'group_id' in data


def test_create_group_too_few_images(auth_client):
    """POST /api/groups with <2 images returns 400."""
    fnames = _upload_images(auth_client, 1)
    resp = auth_client.post('/api/groups',
                            json={'images': fnames},
                            content_type='application/json')
    assert resp.status_code == 400
    assert 'at least 2' in resp.get_json()['error']


def test_list_groups(auth_client):
    """GET /api/groups returns created groups."""
    fnames = _upload_images(auth_client, 2)
    create_resp = auth_client.post('/api/groups',
                                   json={'images': fnames},
                                   content_type='application/json')
    group_id = create_resp.get_json()['group_id']

    resp = auth_client.get('/api/groups')
    assert resp.status_code == 200
    groups = resp.get_json()['groups']
    assert group_id in groups
    assert groups[group_id]['images'] == fnames


def test_update_group_mat_color(auth_client):
    """PATCH /api/groups/<id> updates mat_color."""
    fnames = _upload_images(auth_client, 2)
    create_resp = auth_client.post('/api/groups',
                                   json={'images': fnames},
                                   content_type='application/json')
    group_id = create_resp.get_json()['group_id']

    resp = auth_client.patch(f'/api/groups/{group_id}',
                             json={'mat_color': '#ff0000'},
                             content_type='application/json')
    assert resp.status_code == 200

    groups = auth_client.get('/api/groups').get_json()['groups']
    assert groups[group_id]['mat_color'] == '#ff0000'


def test_update_group_mat_finish_and_bevel(auth_client):
    """PATCH /api/groups/<id> updates mat_finish and bevel_width."""
    fnames = _upload_images(auth_client, 2)
    create_resp = auth_client.post('/api/groups',
                                   json={'images': fnames},
                                   content_type='application/json')
    group_id = create_resp.get_json()['group_id']

    resp = auth_client.patch(f'/api/groups/{group_id}',
                             json={'mat_finish': 'linen', 'bevel_width': 8},
                             content_type='application/json')
    assert resp.status_code == 200

    groups = auth_client.get('/api/groups').get_json()['groups']
    assert groups[group_id]['mat_finish'] == 'linen'
    assert groups[group_id]['bevel_width'] == 8


def test_update_group_scales(auth_client):
    """PATCH /api/groups/<id> updates per-image scales."""
    fnames = _upload_images(auth_client, 2)
    create_resp = auth_client.post('/api/groups',
                                   json={'images': fnames},
                                   content_type='application/json')
    group_id = create_resp.get_json()['group_id']

    scales = {fnames[0]: 1.5, fnames[1]: 0.8}
    resp = auth_client.patch(f'/api/groups/{group_id}',
                             json={'scales': scales},
                             content_type='application/json')
    assert resp.status_code == 200

    groups = auth_client.get('/api/groups').get_json()['groups']
    assert groups[group_id]['scales'] == scales


def test_update_group_images_too_few(auth_client):
    """PATCH /api/groups/<id> with <2 images returns 400."""
    fnames = _upload_images(auth_client, 2)
    create_resp = auth_client.post('/api/groups',
                                   json={'images': fnames},
                                   content_type='application/json')
    group_id = create_resp.get_json()['group_id']

    resp = auth_client.patch(f'/api/groups/{group_id}',
                             json={'images': [fnames[0]]},
                             content_type='application/json')
    assert resp.status_code == 400


def test_update_nonexistent_group(auth_client):
    """PATCH /api/groups/<bad_id> returns 404."""
    resp = auth_client.patch('/api/groups/nonexistent',
                             json={'mat_color': '#000'},
                             content_type='application/json')
    assert resp.status_code == 404


def test_delete_group(auth_client):
    """DELETE /api/groups/<id> removes the group."""
    fnames = _upload_images(auth_client, 2)
    create_resp = auth_client.post('/api/groups',
                                   json={'images': fnames},
                                   content_type='application/json')
    group_id = create_resp.get_json()['group_id']

    resp = auth_client.delete(f'/api/groups/{group_id}')
    assert resp.status_code == 200

    groups = auth_client.get('/api/groups').get_json()['groups']
    assert group_id not in groups


def test_delete_nonexistent_group(auth_client):
    """DELETE /api/groups/<bad_id> returns 404."""
    resp = auth_client.delete('/api/groups/nonexistent')
    assert resp.status_code == 404


def test_api_images_returns_group_slides(auth_client):
    """GET /api/images includes group slides with correct structure."""
    fnames = _upload_images(auth_client, 2)
    create_resp = auth_client.post('/api/groups',
                                   json={'images': fnames, 'mat_color': '#123456'},
                                   content_type='application/json')
    group_id = create_resp.get_json()['group_id']

    resp = auth_client.get('/api/images')
    data = resp.get_json()
    group_slide = next((s for s in data['slides'] if s['type'] == 'group'), None)
    assert group_slide is not None
    assert group_slide['group_id'] == group_id
    assert group_slide['mat_color'] == '#123456'
    assert len(group_slide['images']) == 2

    # Grouped images should not appear as singles
    single_fnames = [s['images'][0]['filename'] for s in data['slides'] if s['type'] == 'single']
    for fn in fnames:
        assert fn not in single_fnames


def test_update_group_border_effect(auth_client):
    """PATCH /api/groups/<id> updates border_effect."""
    fnames = _upload_images(auth_client, 2)
    create_resp = auth_client.post('/api/groups',
                                   json={'images': fnames},
                                   content_type='application/json')
    group_id = create_resp.get_json()['group_id']

    resp = auth_client.patch(f'/api/groups/{group_id}',
                             json={'border_effect': 'shadow'},
                             content_type='application/json')
    assert resp.status_code == 200

    groups = auth_client.get('/api/groups').get_json()['groups']
    assert groups[group_id]['border_effect'] == 'shadow'


def test_update_group_border_effect_null(auth_client):
    """PATCH /api/groups/<id> with border_effect null clears override."""
    fnames = _upload_images(auth_client, 2)
    create_resp = auth_client.post('/api/groups',
                                   json={'images': fnames},
                                   content_type='application/json')
    group_id = create_resp.get_json()['group_id']

    # Set then clear
    auth_client.patch(f'/api/groups/{group_id}',
                      json={'border_effect': 'shadow'},
                      content_type='application/json')
    resp = auth_client.patch(f'/api/groups/{group_id}',
                             json={'border_effect': None},
                             content_type='application/json')
    assert resp.status_code == 200

    groups = auth_client.get('/api/groups').get_json()['groups']
    assert groups[group_id]['border_effect'] is None


def test_groups_require_auth(client):
    """Groups API endpoints require authentication."""
    assert client.get('/api/groups').status_code == 401
    assert client.post('/api/groups', json={'images': []}).status_code == 401
    assert client.patch('/api/groups/x', json={}).status_code == 401
    assert client.delete('/api/groups/x').status_code == 401
