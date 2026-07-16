"""Tests for the upload endpoint."""

import io
from unittest.mock import patch

from PIL import Image

from tests.conftest import make_test_image
import app as photo_app


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


def test_invalid_image_returns_friendly_400_before_hashing(auth_client):
    with patch('app.compute_phash') as compute_hash:
        resp = auth_client.post('/api/upload',
                                data={'files': (io.BytesIO(b'not really png'), 'bad.png')},
                                content_type='multipart/form-data')
    assert resp.status_code == 400
    assert 'valid supported image' in resp.get_json()['errors'][0]
    compute_hash.assert_not_called()
    assert list(photo_app.UPLOAD_FOLDER.glob('*.upload')) == []
    assert [path for path in photo_app.UPLOAD_FOLDER.iterdir()
            if path.is_file() and path.name != 'thumbnails'] == []


def test_excessive_dimension_is_rejected_without_partial_file(auth_client):
    image = Image.new('RGB', (photo_app.MAX_IMAGE_DIMENSION + 1, 1), 'red')
    buffer = io.BytesIO()
    image.save(buffer, format='PNG')
    buffer.seek(0)
    resp = auth_client.post('/api/upload', data={'files': (buffer, 'wide.png')},
                            content_type='multipart/form-data')
    assert resp.status_code == 400
    assert 'dimensions exceed' in resp.get_json()['errors'][0]
    assert list(photo_app.UPLOAD_FOLDER.glob('*.upload')) == []


def test_decompression_bomb_warning_is_converted_to_validation_error(tmp_path):
    candidate = tmp_path / 'bomb.png'
    candidate.write_bytes(b'placeholder')
    with patch('app.Image.open', side_effect=Image.DecompressionBombWarning('bomb')):
        try:
            photo_app.validate_image(candidate)
            assert False, 'expected validation error'
        except ValueError as error:
            assert 'too large' in str(error)


def test_duplicate_check_rejects_invalid_decode_and_cleans_temp(auth_client):
    resp = auth_client.post('/api/check-duplicates',
                            data={'files': (io.BytesIO(b'bad'), 'bad.png')},
                            content_type='multipart/form-data')
    assert resp.status_code == 400
    assert 'valid supported image' in resp.get_json()['errors'][0]
