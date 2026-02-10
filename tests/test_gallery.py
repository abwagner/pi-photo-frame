"""Tests for gallery API: scale, metadata, and image listing."""

import json

from tests.conftest import make_test_image


def _upload_image(auth_client, image_buf=None, filename='test.png'):
    """Helper: upload an image and return the response data."""
    if image_buf is None:
        image_buf = make_test_image(1920, 1080, 'blue')
    data = {'files': (image_buf, filename)}
    resp = auth_client.post('/api/upload', data=data, content_type='multipart/form-data')
    return resp.get_json()


def test_api_images_default_scale(auth_client):
    """GET /api/images returns scale 1.0 for images without explicit scale."""
    result = _upload_image(auth_client)
    fname = result['uploaded'][0]

    resp = auth_client.get('/api/images')
    data = resp.get_json()
    slides = data['slides']
    single_slide = next(s for s in slides if s['type'] == 'single'
                        and s['images'][0]['filename'] == fname)
    assert single_slide['images'][0]['scale'] == 1.0


def test_patch_other_fields_still_work(auth_client):
    """PATCH enabled and mat_color still work (regression)."""
    result = _upload_image(auth_client)
    fname = result['uploaded'][0]

    resp = auth_client.patch(f'/api/gallery/{fname}',
                             json={'enabled': False, 'mat_color': '#ff0000'},
                             content_type='application/json')
    assert resp.status_code == 200

    gallery_resp = auth_client.get('/api/gallery')
    images = gallery_resp.get_json()['images']
    img = next(i for i in images if i['filename'] == fname)
    assert img['enabled'] is False
    assert img['mat_color'] == '#ff0000'


def test_gallery_list_includes_metadata(auth_client):
    """GET /api/gallery returns all expected metadata fields."""
    result = _upload_image(auth_client)
    fname = result['uploaded'][0]

    gallery_resp = auth_client.get('/api/gallery')
    images = gallery_resp.get_json()['images']
    img = next(i for i in images if i['filename'] == fname)

    # Check all expected fields exist
    assert 'enabled' in img
    assert 'width' in img
    assert 'height' in img
    assert 'uploaded_by' in img
    assert 'uploaded_at' in img
    assert 'mat_finish' in img
    assert 'bevel_width' in img


# ===== Mat Finish Tests =====

def test_patch_mat_finish(auth_client):
    """PATCH /api/gallery/<file> with mat_finish updates metadata."""
    result = _upload_image(auth_client)
    fname = result['uploaded'][0]

    resp = auth_client.patch(f'/api/gallery/{fname}',
                             json={'mat_finish': 'linen'},
                             content_type='application/json')
    assert resp.status_code == 200

    gallery_resp = auth_client.get('/api/gallery')
    images = gallery_resp.get_json()['images']
    img = next(i for i in images if i['filename'] == fname)
    assert img['mat_finish'] == 'linen'


def test_patch_mat_finish_null(auth_client):
    """PATCH mat_finish to null clears per-image override."""
    result = _upload_image(auth_client)
    fname = result['uploaded'][0]

    # Set then clear
    auth_client.patch(f'/api/gallery/{fname}',
                      json={'mat_finish': 'suede'},
                      content_type='application/json')
    resp = auth_client.patch(f'/api/gallery/{fname}',
                             json={'mat_finish': None},
                             content_type='application/json')
    assert resp.status_code == 200

    gallery_resp = auth_client.get('/api/gallery')
    images = gallery_resp.get_json()['images']
    img = next(i for i in images if i['filename'] == fname)
    assert img['mat_finish'] is None


def test_patch_bevel_width(auth_client):
    """PATCH /api/gallery/<file> with bevel_width updates metadata."""
    result = _upload_image(auth_client)
    fname = result['uploaded'][0]

    resp = auth_client.patch(f'/api/gallery/{fname}',
                             json={'bevel_width': 8},
                             content_type='application/json')
    assert resp.status_code == 200

    gallery_resp = auth_client.get('/api/gallery')
    images = gallery_resp.get_json()['images']
    img = next(i for i in images if i['filename'] == fname)
    assert img['bevel_width'] == 8


def test_patch_bevel_width_zero(auth_client):
    """PATCH bevel_width to 0 disables bevel for that image."""
    result = _upload_image(auth_client)
    fname = result['uploaded'][0]

    resp = auth_client.patch(f'/api/gallery/{fname}',
                             json={'bevel_width': 0},
                             content_type='application/json')
    assert resp.status_code == 200

    gallery_resp = auth_client.get('/api/gallery')
    images = gallery_resp.get_json()['images']
    img = next(i for i in images if i['filename'] == fname)
    assert img['bevel_width'] == 0


def test_api_images_includes_mat_finish_and_bevel(auth_client):
    """GET /api/images returns mat_finish and bevel_width in slides."""
    result = _upload_image(auth_client)
    fname = result['uploaded'][0]

    auth_client.patch(f'/api/gallery/{fname}',
                      json={'mat_finish': 'silk', 'bevel_width': 12},
                      content_type='application/json')

    resp = auth_client.get('/api/images')
    data = resp.get_json()
    slides = data['slides']
    slide = next(s for s in slides if s['type'] == 'single'
                 and s['images'][0]['filename'] == fname)
    assert slide['images'][0]['mat_finish'] == 'silk'
    assert slide['images'][0]['bevel_width'] == 12


def test_settings_mat_finish(auth_client):
    """POST /api/settings with mat_finish updates global setting."""
    resp = auth_client.post('/api/settings',
                            json={'mat_finish': 'suede'},
                            content_type='application/json')
    assert resp.status_code == 200

    settings_resp = auth_client.get('/api/settings')
    settings = settings_resp.get_json()
    assert settings['mat_finish'] == 'suede'


def test_settings_bevel_width(auth_client):
    """POST /api/settings with bevel_width updates global setting."""
    resp = auth_client.post('/api/settings',
                            json={'bevel_width': 10},
                            content_type='application/json')
    assert resp.status_code == 200

    settings_resp = auth_client.get('/api/settings')
    settings = settings_resp.get_json()
    assert settings['bevel_width'] == 10


def test_settings_defaults_include_mat_fields(auth_client):
    """Default settings include mat_finish and bevel_width."""
    settings_resp = auth_client.get('/api/settings')
    settings = settings_resp.get_json()
    assert settings['mat_finish'] == 'flat'
    assert settings['bevel_width'] == 4
