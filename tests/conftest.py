"""Shared fixtures for pi-photo-frame tests."""

import io
import json
import shutil
import tempfile
from pathlib import Path

import pytest
from PIL import Image

# Import the Flask app
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
import app as photo_app


@pytest.fixture
def tmp_dirs(tmp_path):
    """Create temporary upload and data directories."""
    upload_dir = tmp_path / "uploads"
    data_dir = tmp_path / "data"
    upload_dir.mkdir()
    data_dir.mkdir()
    return upload_dir, data_dir


@pytest.fixture
def app(tmp_dirs):
    """Create a Flask test app with temp dirs."""
    upload_dir, data_dir = tmp_dirs

    # Override module-level paths
    original_upload = photo_app.UPLOAD_FOLDER
    original_thumbnail = photo_app.THUMBNAIL_FOLDER
    original_data = photo_app.DATA_FOLDER
    original_settings = photo_app.SETTINGS_FILE
    original_users = photo_app.USERS_FILE
    original_gallery = photo_app.GALLERY_FILE

    thumb_dir = upload_dir / "thumbnails"
    thumb_dir.mkdir()

    photo_app.UPLOAD_FOLDER = upload_dir
    photo_app.THUMBNAIL_FOLDER = thumb_dir
    photo_app.DATA_FOLDER = data_dir
    photo_app.SETTINGS_FILE = data_dir / "settings.json"
    photo_app.USERS_FILE = data_dir / "users.json"
    photo_app.GALLERY_FILE = data_dir / "gallery.json"
    photo_app.app.config['UPLOAD_FOLDER'] = upload_dir

    photo_app.app.config['TESTING'] = True
    photo_app.app.config['WTF_CSRF_ENABLED'] = False
    photo_app.app.config['SECRET_KEY'] = 'test-secret-key'

    yield photo_app.app

    # Restore original paths
    photo_app.UPLOAD_FOLDER = original_upload
    photo_app.THUMBNAIL_FOLDER = original_thumbnail
    photo_app.DATA_FOLDER = original_data
    photo_app.SETTINGS_FILE = original_settings
    photo_app.USERS_FILE = original_users
    photo_app.GALLERY_FILE = original_gallery


@pytest.fixture
def client(app):
    """Flask test client."""
    return app.test_client()


@pytest.fixture
def auth_client(app):
    """Flask test client with authenticated admin session."""
    client = app.test_client()
    # Create default admin user by loading users (triggers default creation)
    photo_app.load_users()
    # Log in
    client.post('/login', data={
        'username': 'admin',
        'password': 'password'
    }, follow_redirects=True)
    return client


def make_test_image(width=100, height=100, color='red', fmt='PNG', pattern=None):
    """Generate a test image as bytes.

    Args:
        pattern: If 'checkerboard', draws a checkerboard pattern using color
                 and black to produce a structurally distinct image.
    """
    img = Image.new('RGB', (width, height), color=color)
    if pattern == 'complex':
        # Draw shapes to create a structurally distinct image for phash differentiation
        from PIL import ImageDraw
        draw = ImageDraw.Draw(img)
        draw.line([(0, 0), (width, height)], fill='green', width=5)
        draw.line([(width, 0), (0, height)], fill='yellow', width=5)
        draw.ellipse([width//8, height//8, width//2, height//2], fill='blue')
        draw.rectangle([width//2, height//2, width*7//8, height*7//8], fill='red')
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    buf.seek(0)
    return buf


@pytest.fixture
def sample_image():
    """A small 100x100 red test image (below 720p threshold)."""
    return make_test_image(100, 100, 'red')


@pytest.fixture
def large_image():
    """A 1920x1080 test image (above 720p threshold)."""
    return make_test_image(1920, 1080, 'blue')


@pytest.fixture
def similar_image():
    """A slightly different version of the sample image (for near-dupe testing)."""
    # Same size, slightly different color — perceptual hash should be close
    return make_test_image(100, 100, '#ff1010')


@pytest.fixture
def different_image():
    """A completely different image (for no-match testing)."""
    return make_test_image(200, 200, 'green')
