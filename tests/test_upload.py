"""Tests for the upload endpoint."""

from tests.conftest import make_test_image


def test_upload_requires_auth(client):
    """POST /api/upload without login is rejected."""
    image_buf = make_test_image()
    resp = client.post('/api/upload',
                       data={'files': (image_buf, 'test.png')},
                       content_type='multipart/form-data')
    # Should redirect to login or return 401
    assert resp.status_code in (302, 401)


def test_upload_valid_image(auth_client, app):
    """Upload a valid image succeeds."""
    import app as photo_app
    image_buf = make_test_image(800, 600, 'green')
    resp = auth_client.post('/api/upload',
                            data={'files': (image_buf, 'photo.png')},
                            content_type='multipart/form-data')
    data = resp.get_json()
    assert resp.status_code == 200
    assert len(data['uploaded']) == 1

    # Verify file exists on disk
    fname = data['uploaded'][0]
    assert (photo_app.UPLOAD_FOLDER / fname).exists()


def test_upload_stores_phash(auth_client):
    """Upload stores a perceptual hash in metadata."""
    image_buf = make_test_image(200, 200, 'red')
    resp = auth_client.post('/api/upload',
                            data={'files': (image_buf, 'test.png')},
                            content_type='multipart/form-data')
    fname = resp.get_json()['uploaded'][0]

    gallery_resp = auth_client.get('/api/gallery')
    images = gallery_resp.get_json()['images']
    img = next(i for i in images if i['filename'] == fname)
    assert img['phash'] is not None
    assert len(img['phash']) > 0


def test_upload_stores_dimensions(auth_client):
    """Upload extracts and stores image dimensions."""
    image_buf = make_test_image(640, 480, 'blue')
    resp = auth_client.post('/api/upload',
                            data={'files': (image_buf, 'test.png')},
                            content_type='multipart/form-data')
    fname = resp.get_json()['uploaded'][0]

    gallery_resp = auth_client.get('/api/gallery')
    images = gallery_resp.get_json()['images']
    img = next(i for i in images if i['filename'] == fname)
    assert img['width'] == 640
    assert img['height'] == 480


def test_upload_invalid_extension(auth_client):
    """Upload of non-image file type returns error."""
    import io
    text_buf = io.BytesIO(b'not an image')
    resp = auth_client.post('/api/upload',
                            data={'files': (text_buf, 'document.txt')},
                            content_type='multipart/form-data')
    data = resp.get_json()
    assert len(data['uploaded']) == 0
    assert len(data['errors']) == 1


def test_upload_stores_scale_default(auth_client):
    """Uploaded images default to scale 1.0."""
    image_buf = make_test_image(200, 200, 'red')
    resp = auth_client.post('/api/upload',
                            data={'files': (image_buf, 'test.png')},
                            content_type='multipart/form-data')
    fname = resp.get_json()['uploaded'][0]

    gallery_resp = auth_client.get('/api/gallery')
    images = gallery_resp.get_json()['images']
    img = next(i for i in images if i['filename'] == fname)
    assert img.get('scale', 1.0) == 1.0
