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
