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


def test_patch_scale(auth_client):
    """PATCH /api/gallery/<file> with scale updates metadata."""
    result = _upload_image(auth_client)
    fname = result['uploaded'][0]

    resp = auth_client.patch(f'/api/gallery/{fname}',
                             json={'scale': 1.5},
                             content_type='application/json')
    assert resp.status_code == 200
    assert resp.get_json()['success'] is True

    # Verify via gallery listing
    gallery_resp = auth_client.get('/api/gallery')
    images = gallery_resp.get_json()['images']
    img = next(i for i in images if i['filename'] == fname)
    assert img['scale'] == 1.5


def test_patch_scale_default(auth_client):
    """Uploaded images default to scale 1.0."""
    result = _upload_image(auth_client)
    fname = result['uploaded'][0]

    gallery_resp = auth_client.get('/api/gallery')
    images = gallery_resp.get_json()['images']
    img = next(i for i in images if i['filename'] == fname)
    assert img.get('scale', 1.0) == 1.0


def test_api_images_includes_scale(auth_client):
    """GET /api/images returns scale in single slides."""
    result = _upload_image(auth_client)
    fname = result['uploaded'][0]

    # Set a non-default scale
    auth_client.patch(f'/api/gallery/{fname}',
                      json={'scale': 2.0},
                      content_type='application/json')

    resp = auth_client.get('/api/images')
    data = resp.get_json()
    slides = data['slides']
    single_slide = next(s for s in slides if s['type'] == 'single'
                        and s['images'][0]['filename'] == fname)
    assert single_slide['images'][0]['scale'] == 2.0


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
    assert 'phash' in img
    assert 'scale' in img
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
    """Default settings include mat_finish, bevel_width, and border_effect."""
    settings_resp = auth_client.get('/api/settings')
    settings = settings_resp.get_json()
    assert settings['mat_finish'] == 'flat'
    assert settings['bevel_width'] == 4
    assert settings['border_effect'] == 'bevel'


# ===== Border Effect Tests =====

def test_patch_border_effect(auth_client):
    """PATCH /api/gallery/<file> with border_effect updates metadata."""
    result = _upload_image(auth_client)
    fname = result['uploaded'][0]

    resp = auth_client.patch(f'/api/gallery/{fname}',
                             json={'border_effect': 'shadow'},
                             content_type='application/json')
    assert resp.status_code == 200

    gallery_resp = auth_client.get('/api/gallery')
    images = gallery_resp.get_json()['images']
    img = next(i for i in images if i['filename'] == fname)
    assert img['border_effect'] == 'shadow'


def test_patch_border_effect_null(auth_client):
    """PATCH border_effect to null clears per-image override."""
    result = _upload_image(auth_client)
    fname = result['uploaded'][0]

    auth_client.patch(f'/api/gallery/{fname}',
                      json={'border_effect': 'shadow'},
                      content_type='application/json')
    resp = auth_client.patch(f'/api/gallery/{fname}',
                             json={'border_effect': None},
                             content_type='application/json')
    assert resp.status_code == 200

    gallery_resp = auth_client.get('/api/gallery')
    images = gallery_resp.get_json()['images']
    img = next(i for i in images if i['filename'] == fname)
    assert img['border_effect'] is None


def test_settings_border_effect(auth_client):
    """POST /api/settings with border_effect updates global setting."""
    resp = auth_client.post('/api/settings',
                            json={'border_effect': 'shadow'},
                            content_type='application/json')
    assert resp.status_code == 200

    settings_resp = auth_client.get('/api/settings')
    settings = settings_resp.get_json()
    assert settings['border_effect'] == 'shadow'


def test_api_images_includes_border_effect(auth_client):
    """GET /api/images returns border_effect in slides."""
    result = _upload_image(auth_client)
    fname = result['uploaded'][0]

    auth_client.patch(f'/api/gallery/{fname}',
                      json={'border_effect': 'shadow'},
                      content_type='application/json')

    resp = auth_client.get('/api/images')
    data = resp.get_json()
    slides = data['slides']
    slide = next(s for s in slides if s['type'] == 'single'
                 and s['images'][0]['filename'] == fname)
    assert slide['images'][0]['border_effect'] == 'shadow'


def test_gallery_list_includes_border_effect(auth_client):
    """GET /api/gallery returns border_effect in metadata."""
    result = _upload_image(auth_client)
    fname = result['uploaded'][0]

    gallery_resp = auth_client.get('/api/gallery')
    images = gallery_resp.get_json()['images']
    img = next(i for i in images if i['filename'] == fname)
    assert 'border_effect' in img


def test_custom_settings_not_overridden_by_defaults(auth_client):
    """Changing default settings does not override per-image custom settings."""
    result = _upload_image(auth_client)
    fname = result['uploaded'][0]

    # Set custom per-image settings
    auth_client.patch(f'/api/gallery/{fname}',
                      json={'mat_color': '#ff0000', 'border_effect': 'shadow', 'bevel_width': 8},
                      content_type='application/json')

    # Change default settings
    auth_client.post('/api/settings',
                     json={'mat_color': '#00ff00', 'border_effect': 'bevel', 'bevel_width': 2},
                     content_type='application/json')

    # Verify per-image settings are preserved
    gallery_resp = auth_client.get('/api/gallery')
    images = gallery_resp.get_json()['images']
    img = next(i for i in images if i['filename'] == fname)
    assert img['mat_color'] == '#ff0000'
    assert img['border_effect'] == 'shadow'
    assert img['bevel_width'] == 8


# ===== Crop Tests =====

def test_patch_crop(auth_client):
    """PATCH /api/gallery/<file> with crop updates metadata."""
    result = _upload_image(auth_client)
    fname = result['uploaded'][0]

    crop = {'x': 0.1, 'y': 0.2, 'w': 0.6, 'h': 0.5}
    resp = auth_client.patch(f'/api/gallery/{fname}',
                             json={'crop': crop},
                             content_type='application/json')
    assert resp.status_code == 200

    gallery_resp = auth_client.get('/api/gallery')
    images = gallery_resp.get_json()['images']
    img = next(i for i in images if i['filename'] == fname)
    assert img['crop'] == crop


def test_patch_crop_null(auth_client):
    """PATCH crop to null clears crop."""
    result = _upload_image(auth_client)
    fname = result['uploaded'][0]

    auth_client.patch(f'/api/gallery/{fname}',
                      json={'crop': {'x': 0, 'y': 0, 'w': 0.5, 'h': 0.5}},
                      content_type='application/json')
    resp = auth_client.patch(f'/api/gallery/{fname}',
                             json={'crop': None},
                             content_type='application/json')
    assert resp.status_code == 200

    gallery_resp = auth_client.get('/api/gallery')
    images = gallery_resp.get_json()['images']
    img = next(i for i in images if i['filename'] == fname)
    assert img['crop'] is None


def test_api_images_includes_crop(auth_client):
    """GET /api/images returns crop in slide data."""
    result = _upload_image(auth_client)
    fname = result['uploaded'][0]

    crop = {'x': 0.1, 'y': 0.1, 'w': 0.8, 'h': 0.8}
    auth_client.patch(f'/api/gallery/{fname}',
                      json={'crop': crop},
                      content_type='application/json')

    resp = auth_client.get('/api/images')
    data = resp.get_json()
    slides = data['slides']
    slide = next(s for s in slides if s['type'] == 'single'
                 and s['images'][0]['filename'] == fname)
    assert slide['images'][0]['crop'] == crop


def test_gallery_list_includes_crop_field(auth_client):
    """GET /api/gallery returns crop in metadata."""
    result = _upload_image(auth_client)
    fname = result['uploaded'][0]

    gallery_resp = auth_client.get('/api/gallery')
    images = gallery_resp.get_json()['images']
    img = next(i for i in images if i['filename'] == fname)
    assert 'crop' in img
