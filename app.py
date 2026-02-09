#!/usr/bin/env python3
"""
Pi Photo Frame - A web-based photo display system for Raspberry Pi
Upload photos via web interface, display on TV with customizable mat colors
"""

import os
import json
import uuid
import secrets
import hashlib
import fcntl
import re
import subprocess
import threading
import logging
from datetime import datetime
from pathlib import Path
from functools import wraps
from flask import Flask, render_template, request, jsonify, send_from_directory, redirect, url_for, session

import bcrypt
from flask_wtf.csrf import CSRFProtect
from werkzeug.utils import secure_filename
import tempfile

from PIL import Image, ImageOps
from apscheduler.schedulers.background import BackgroundScheduler
import imagehash

app = Flask(__name__)
csrf = CSRFProtect(app)

# Configuration
UPLOAD_FOLDER = Path(__file__).parent / 'uploads'
DATA_FOLDER = Path(__file__).parent / 'data'
SETTINGS_FILE = DATA_FOLDER / 'settings.json'
USERS_FILE = DATA_FOLDER / 'users.json'
GALLERY_FILE = DATA_FOLDER / 'gallery.json'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'bmp'}
RCLONE_CONFIG_DIR = DATA_FOLDER / 'rclone'
RCLONE_CONFIG_FILE = RCLONE_CONFIG_DIR / 'rclone.conf'
BACKUP_LOG_FILE = DATA_FOLDER / 'backup_log.json'
BACKUP_LOCK_FILE = DATA_FOLDER / '.backup.lock'

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB max upload

# Ensure folders exist
UPLOAD_FOLDER.mkdir(exist_ok=True)
DATA_FOLDER.mkdir(exist_ok=True)

# Generate a secret key for sessions (persisted so sessions survive restarts)
SECRET_KEY_FILE = DATA_FOLDER / '.secret_key'
if SECRET_KEY_FILE.exists():
    app.secret_key = SECRET_KEY_FILE.read_text().strip()
else:
    app.secret_key = secrets.token_hex(32)
    SECRET_KEY_FILE.write_text(app.secret_key)
    os.chmod(SECRET_KEY_FILE, 0o600)

# Display token for kiosk mode
DISPLAY_TOKEN_FILE = DATA_FOLDER / '.display_token'
if DISPLAY_TOKEN_FILE.exists():
    DISPLAY_TOKEN = DISPLAY_TOKEN_FILE.read_text().strip()
else:
    DISPLAY_TOKEN = secrets.token_urlsafe(32)
    DISPLAY_TOKEN_FILE.write_text(DISPLAY_TOKEN)
try:
    os.chmod(DISPLAY_TOKEN_FILE, 0o600)
except OSError:
    pass

# Session cookie security
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
# Enable Secure flag when behind HTTPS (set env var SECURE_COOKIES=1)
if os.environ.get('SECURE_COOKIES', '').lower() in ('1', 'true'):
    app.config['SESSION_COOKIE_SECURE'] = True

# Reverse proxy support — enable with BEHIND_PROXY=1
if os.environ.get('BEHIND_PROXY', '').lower() in ('1', 'true'):
    from werkzeug.middleware.proxy_fix import ProxyFix
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)


# ============ User Management ============

def hash_password(password: str, salt: str = None) -> tuple:
    """Hash a password using bcrypt.

    The salt parameter is accepted for backwards compatibility with legacy
    SHA-256 hashes but is ignored for new bcrypt hashes.
    """
    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    return hashed, None


def _verify_legacy_sha256(password: str, stored_hash: str, salt: str) -> bool:
    """Verify a password against a legacy salted SHA-256 hash."""
    candidate = hashlib.sha256((salt + password).encode()).hexdigest()
    return secrets.compare_digest(candidate, stored_hash)


def _is_bcrypt_hash(stored_hash: str) -> bool:
    """Check if a stored hash is in bcrypt format."""
    return stored_hash.startswith('$2b$') or stored_hash.startswith('$2a$')


def load_users():
    """Load users from JSON file, create default admin if none exist"""
    if USERS_FILE.exists():
        with open(USERS_FILE, 'r') as f:
            return json.load(f)

    # Create default admin user
    hashed, salt = hash_password('password')
    users = {
        'admin': {
            'password_hash': hashed,
            'salt': salt,
            'role': 'admin',
            'created': datetime.now().isoformat()
        }
    }
    save_users(users)
    return users


def save_users(users):
    """Save users to JSON file"""
    with open(USERS_FILE, 'w') as f:
        json.dump(users, f, indent=2)
    os.chmod(USERS_FILE, 0o600)


def verify_user(username: str, password: str) -> bool:
    """Verify username and password, auto-migrating legacy SHA-256 hashes to bcrypt."""
    users = load_users()
    if username not in users:
        return False
    user = users[username]

    if _is_bcrypt_hash(user['password_hash']):
        if not bcrypt.checkpw(password.encode(), user['password_hash'].encode()):
            return False
    else:
        # Legacy salted SHA-256
        if not _verify_legacy_sha256(password, user['password_hash'], user.get('salt', '')):
            return False
        # Auto-migrate to bcrypt on successful login
        new_hash, _ = hash_password(password)
        user['password_hash'] = new_hash
        user['salt'] = None
        save_users(users)

    return True


def has_default_password(username):
    """Check if user still has the default password."""
    users = load_users()
    if username not in users:
        return False
    user = users[username]
    if _is_bcrypt_hash(user['password_hash']):
        return bcrypt.checkpw(b'password', user['password_hash'].encode())
    return _verify_legacy_sha256('password', user['password_hash'], user.get('salt', ''))


def get_user_role(username: str) -> str:
    """Get user's role"""
    users = load_users()
    if username in users:
        return users[username].get('role', 'user')
    return None


def create_user(username: str, password: str, role: str = 'user') -> tuple:
    """Create a new user. Returns (success, message)"""
    users = load_users()

    if username in users:
        return False, 'Username already exists'

    if len(username) < 3:
        return False, 'Username must be at least 3 characters'

    if len(password) < 4:
        return False, 'Password must be at least 4 characters'

    if role not in ['admin', 'user']:
        return False, 'Invalid role'

    hashed, salt = hash_password(password)
    users[username] = {
        'password_hash': hashed,
        'salt': salt,
        'role': role,
        'created': datetime.now().isoformat()
    }
    save_users(users)
    return True, 'User created successfully'


def delete_user(username: str) -> tuple:
    """Delete a user. Returns (success, message)"""
    users = load_users()

    if username not in users:
        return False, 'User not found'

    if username == 'admin':
        return False, 'Cannot delete the admin user'

    del users[username]
    save_users(users)
    return True, 'User deleted successfully'


def change_user_password(username: str, new_password: str) -> tuple:
    """Change a user's password. Returns (success, message)"""
    users = load_users()

    if username not in users:
        return False, 'User not found'

    if len(new_password) < 4:
        return False, 'Password must be at least 4 characters'

    hashed, salt = hash_password(new_password)
    users[username]['password_hash'] = hashed
    users[username]['salt'] = salt
    save_users(users)
    return True, 'Password changed successfully'


# ============ Authentication Decorators ============

def is_authenticated():
    """Check if current session is authenticated"""
    return session.get('authenticated', False)


def is_admin():
    """Check if current user is admin"""
    if not is_authenticated():
        return False
    username = session.get('username')
    return get_user_role(username) == 'admin'


def login_required(f):
    """Decorator to require authentication"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not is_authenticated():
            return redirect(url_for('login'))
        if has_default_password(session.get('username')) and request.path != '/change-password':
            return redirect(url_for('change_password', forced=1))
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    """Decorator to require admin role"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not is_authenticated():
            return redirect(url_for('login'))
        if not is_admin():
            return render_template('error.html', message='Admin access required'), 403
        return f(*args, **kwargs)
    return decorated_function


def api_login_required(f):
    """Decorator for API endpoints - returns 401 instead of redirect"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not is_authenticated():
            return jsonify({'error': 'Authentication required'}), 401
        return f(*args, **kwargs)
    return decorated_function


def api_admin_required(f):
    """Decorator for admin API endpoints"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not is_authenticated():
            return jsonify({'error': 'Authentication required'}), 401
        if not is_admin():
            return jsonify({'error': 'Admin access required'}), 403
        return f(*args, **kwargs)
    return decorated_function


# ============ Gallery Management ============

def load_gallery():
    """Load gallery metadata"""
    if GALLERY_FILE.exists():
        with open(GALLERY_FILE, 'r') as f:
            data = json.load(f)
            if 'groups' not in data:
                data['groups'] = {}
            return data
    return {'images': {}, 'groups': {}}


def save_gallery(gallery):
    """Save gallery metadata"""
    with open(GALLERY_FILE, 'w') as f:
        json.dump(gallery, f, indent=2)


def get_image_metadata(filename):
    """Get metadata for a single image"""
    gallery = load_gallery()
    return gallery['images'].get(filename, {
        'enabled': True,
        'title': '',
        'uploaded_at': None,
        'uploaded_by': None,
        'width': None,
        'height': None,
        'mat_color': None,
        'phash': None,
        'scale': 1.0
    })


def update_image_metadata(filename, **kwargs):
    """Update metadata for an image"""
    gallery = load_gallery()
    if filename not in gallery['images']:
        gallery['images'][filename] = {
            'enabled': True,
            'title': '',
            'uploaded_at': None,
            'uploaded_by': None,
            'width': None,
            'height': None,
            'mat_color': None,
            'phash': None,
            'scale': 1.0
        }
    gallery['images'][filename].update(kwargs)
    save_gallery(gallery)


def remove_image_metadata(filename):
    """Remove metadata for an image"""
    gallery = load_gallery()
    if filename in gallery['images']:
        del gallery['images'][filename]
        save_gallery(gallery)


def get_grouped_filenames():
    """Get set of all filenames that belong to a group"""
    gallery = load_gallery()
    grouped = set()
    for group in gallery['groups'].values():
        grouped.update(group.get('images', []))
    return grouped


def remove_filename_from_groups(filename):
    """Remove a filename from any groups it belongs to, delete empty groups"""
    gallery = load_gallery()
    groups_to_delete = []
    for group_id, group in gallery['groups'].items():
        if filename in group.get('images', []):
            group['images'].remove(filename)
            if len(group['images']) < 2:
                groups_to_delete.append(group_id)
    for gid in groups_to_delete:
        del gallery['groups'][gid]
    if groups_to_delete or any(filename in g.get('images', []) for g in gallery['groups'].values()):
        save_gallery(gallery)


def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def compute_phash(filepath):
    """Compute perceptual hash of an image file. Returns hex string or None."""
    try:
        with Image.open(filepath) as img:
            oriented = ImageOps.exif_transpose(img)
            return str(imagehash.phash(oriented))
    except Exception:
        return None


def get_uploaded_images():
    """Get list of all uploaded images with metadata"""
    if not UPLOAD_FOLDER.exists():
        return []

    gallery = load_gallery()
    images = []

    for f in sorted(UPLOAD_FOLDER.iterdir()):
        if f.is_file() and allowed_file(f.name):
            meta = gallery['images'].get(f.name, {
                'enabled': True,
                'title': '',
                'uploaded_at': None,
                'uploaded_by': None,
                'width': None,
                'height': None,
                'mat_color': None,
                'phash': None,
                'scale': 1.0
            })
            images.append({
                'filename': f.name,
                'size': f.stat().st_size,
                'modified': datetime.fromtimestamp(f.stat().st_mtime).isoformat(),
                **meta
            })

    return images


def get_enabled_images():
    """Get list of enabled images only (for display)"""
    return [img for img in get_uploaded_images() if img.get('enabled', True)]


# ============ Settings ============

DEFAULT_SETTINGS = {
    'mat_color': '#2c2c2c',
    'slideshow_interval': 10,
    'transition_duration': 1,
    'fit_mode': 'contain',
    'shuffle': False,
    'image_order': [],
    'target_aspect_ratio': '16:9',
    'tv_schedules': []
}


def load_settings():
    """Load settings from JSON file"""
    if SETTINGS_FILE.exists():
        with open(SETTINGS_FILE, 'r') as f:
            settings = json.load(f)
            return {**DEFAULT_SETTINGS, **settings}
    return DEFAULT_SETTINGS.copy()


def save_settings(settings):
    """Save settings to JSON file"""
    with open(SETTINGS_FILE, 'w') as f:
        json.dump(settings, f, indent=2)


# ============ Backup Management ============

backup_lock = threading.Lock()
backup_in_progress = False


def load_backup_log():
    """Load backup log from JSON file"""
    if BACKUP_LOG_FILE.exists():
        with open(BACKUP_LOG_FILE, 'r') as f:
            return json.load(f)
    return {'last_backup': None, 'last_result': None, 'last_error': None, 'history': []}


def save_backup_log(log_data):
    """Save backup log to JSON file"""
    # Keep only last 30 history entries
    if len(log_data.get('history', [])) > 30:
        log_data['history'] = log_data['history'][-30:]
    with open(BACKUP_LOG_FILE, 'w') as f:
        json.dump(log_data, f, indent=2)


def is_backup_configured():
    """Check if rclone is configured for Dropbox"""
    if not RCLONE_CONFIG_FILE.exists():
        return False
    content = RCLONE_CONFIG_FILE.read_text()
    return '[dropbox]' in content


def generate_rclone_config(token):
    """Generate rclone.conf for Dropbox with the given token"""
    RCLONE_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    config_content = f"""[dropbox]
type = dropbox
token = {token}
"""
    RCLONE_CONFIG_FILE.write_text(config_content)
    os.chmod(RCLONE_CONFIG_FILE, 0o600)


def get_backup_settings():
    """Get backup-specific settings"""
    settings = load_settings()
    return {
        'backup_time': settings.get('backup_time', os.environ.get('BACKUP_TIME', '03:00')),
        'backup_path': settings.get('backup_path', 'PhotoFrameBackup')
    }


def run_backup():
    """Run rclone backup to Dropbox"""
    global backup_in_progress

    if not is_backup_configured():
        return {'success': False, 'error': 'Backup not configured'}

    # File-based lock to prevent concurrent runs across workers
    try:
        lock_fd = open(BACKUP_LOCK_FILE, 'w')
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except (IOError, OSError):
        return {'success': False, 'error': 'Backup already in progress'}

    backup_in_progress = True
    start_time = datetime.now()
    log = load_backup_log()

    try:
        backup_settings = get_backup_settings()
        remote_path = backup_settings['backup_path']
        config = str(RCLONE_CONFIG_FILE)

        # Sync uploads
        result1 = subprocess.run(
            ['rclone', 'sync', str(UPLOAD_FOLDER), f'dropbox:{remote_path}/uploads',
             '--config', config],
            capture_output=True, text=True, timeout=3600
        )

        # Sync data (excluding secrets, credentials, and lock files)
        result2 = subprocess.run(
            ['rclone', 'sync', str(DATA_FOLDER), f'dropbox:{remote_path}/data',
             '--config', config,
             '--exclude', 'rclone/**',
             '--exclude', '.backup.lock',
             '--exclude', '.secret_key',
             '--exclude', '.display_token',
             '--exclude', 'users.json'],
            capture_output=True, text=True, timeout=3600
        )

        duration = (datetime.now() - start_time).total_seconds()

        if result1.returncode != 0 or result2.returncode != 0:
            error_msg = (result1.stderr or '') + (result2.stderr or '')
            error_msg = error_msg.strip()[:500]
            log['last_backup'] = start_time.isoformat()
            log['last_result'] = 'error'
            log['last_error'] = error_msg
            log['history'].append({
                'timestamp': start_time.isoformat(),
                'result': 'error',
                'error': error_msg,
                'duration_seconds': round(duration, 1)
            })
            save_backup_log(log)
            return {'success': False, 'error': error_msg}

        log['last_backup'] = start_time.isoformat()
        log['last_result'] = 'success'
        log['last_error'] = None
        log['history'].append({
            'timestamp': start_time.isoformat(),
            'result': 'success',
            'duration_seconds': round(duration, 1)
        })
        save_backup_log(log)
        return {'success': True, 'duration_seconds': round(duration, 1)}

    except subprocess.TimeoutExpired:
        log['last_backup'] = start_time.isoformat()
        log['last_result'] = 'error'
        log['last_error'] = 'Backup timed out after 1 hour'
        log['history'].append({
            'timestamp': start_time.isoformat(),
            'result': 'error',
            'error': 'Backup timed out after 1 hour'
        })
        save_backup_log(log)
        return {'success': False, 'error': 'Backup timed out'}

    except Exception as e:
        error_msg = str(e)[:500]
        log['last_backup'] = start_time.isoformat()
        log['last_result'] = 'error'
        log['last_error'] = error_msg
        log['history'].append({
            'timestamp': start_time.isoformat(),
            'result': 'error',
            'error': error_msg
        })
        save_backup_log(log)
        return {'success': False, 'error': error_msg}

    finally:
        backup_in_progress = False
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
            lock_fd.close()
        except Exception:
            pass


def run_backup_async():
    """Run backup in a background thread"""
    thread = threading.Thread(target=run_backup, daemon=True)
    thread.start()


restore_in_progress = False


def run_restore():
    """Restore photos and data from Dropbox backup"""
    global restore_in_progress

    if not is_backup_configured():
        return {'success': False, 'error': 'Backup not configured'}

    # Reuse the same file lock to prevent backup and restore from running concurrently
    try:
        lock_fd = open(BACKUP_LOCK_FILE, 'w')
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except (IOError, OSError):
        return {'success': False, 'error': 'A backup or restore is already in progress'}

    restore_in_progress = True
    start_time = datetime.now()

    try:
        backup_settings = get_backup_settings()
        remote_path = backup_settings['backup_path']
        config = str(RCLONE_CONFIG_FILE)

        # Restore uploads (use copy so we don't delete local files missing from remote)
        result1 = subprocess.run(
            ['rclone', 'copy', f'dropbox:{remote_path}/uploads', str(UPLOAD_FOLDER),
             '--config', config],
            capture_output=True, text=True, timeout=3600
        )

        # Restore data (excluding rclone config, lock file, secret key, and users)
        result2 = subprocess.run(
            ['rclone', 'copy', f'dropbox:{remote_path}/data', str(DATA_FOLDER),
             '--config', config,
             '--exclude', 'rclone/**',
             '--exclude', '.backup.lock',
             '--exclude', '.secret_key',
             '--exclude', 'users.json'],
            capture_output=True, text=True, timeout=3600
        )

        duration = (datetime.now() - start_time).total_seconds()

        if result1.returncode != 0 or result2.returncode != 0:
            error_msg = (result1.stderr or '') + (result2.stderr or '')
            return {'success': False, 'error': error_msg.strip()[:500]}

        return {'success': True, 'duration_seconds': round(duration, 1)}

    except subprocess.TimeoutExpired:
        return {'success': False, 'error': 'Restore timed out after 1 hour'}

    except Exception as e:
        return {'success': False, 'error': str(e)[:500]}

    finally:
        restore_in_progress = False
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
            lock_fd.close()
        except Exception:
            pass


def run_restore_async():
    """Run restore in a background thread"""
    thread = threading.Thread(target=run_restore, daemon=True)
    thread.start()


# ============ Backup Scheduler ============

scheduler = BackgroundScheduler(daemon=True)


def init_scheduler():
    """Initialize the daily backup scheduler"""
    backup_settings = get_backup_settings()
    backup_time = backup_settings['backup_time']
    try:
        hour, minute = map(int, backup_time.split(':'))
    except ValueError:
        hour, minute = 3, 0

    scheduler.add_job(
        run_backup,
        'cron',
        hour=hour,
        minute=minute,
        id='daily_backup',
        replace_existing=True,
        misfire_grace_time=3600
    )
    if not scheduler.running:
        scheduler.start()


def reschedule_backup(time_str):
    """Reschedule the daily backup to a new time"""
    try:
        hour, minute = map(int, time_str.split(':'))
    except ValueError:
        return

    if scheduler.get_job('daily_backup'):
        scheduler.reschedule_job(
            'daily_backup',
            trigger='cron',
            hour=hour,
            minute=minute
        )


# Start scheduler on module load
init_scheduler()


# ============ CEC TV Control ============

def is_cec_available():
    """Check if cec-client is installed and a CEC device is accessible."""
    try:
        result = subprocess.run(
            ['cec-client', '--list-devices'],
            capture_output=True, text=True, timeout=5
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def cec_send_command(command):
    """Send a CEC command via cec-client. Returns dict with success and optional error."""
    cec_map = {'on': 'on 0', 'standby': 'standby 0'}
    cec_str = cec_map.get(command)
    if not cec_str:
        return {'success': False, 'error': f'Unknown command: {command}'}
    try:
        result = subprocess.run(
            ['cec-client', '-s', '-d', '1'],
            input=cec_str + '\n',
            capture_output=True, text=True, timeout=10
        )
        return {'success': result.returncode == 0,
                'error': result.stderr.strip()[:200] if result.returncode != 0 else None}
    except FileNotFoundError:
        return {'success': False, 'error': 'cec-client not installed'}
    except subprocess.TimeoutExpired:
        return {'success': False, 'error': 'CEC command timed out'}


def schedule_cec_jobs():
    """(Re-)schedule all CEC on/off jobs from settings."""
    for job in scheduler.get_jobs():
        if job.id.startswith('cec_'):
            scheduler.remove_job(job.id)

    settings = load_settings()
    for sched in settings.get('tv_schedules', []):
        if not sched.get('enabled', True):
            continue

        sched_id = sched.get('id', '')
        days = sched.get('days', [])
        if not days:
            continue

        day_of_week = ','.join(str(d) for d in sorted(days))

        on_h, on_m = map(int, sched['on_time'].split(':'))
        scheduler.add_job(
            cec_send_command, 'cron',
            args=['on'],
            day_of_week=day_of_week,
            hour=on_h, minute=on_m,
            id=f'cec_{sched_id}_on',
            replace_existing=True,
            misfire_grace_time=300
        )

        off_h, off_m = map(int, sched['off_time'].split(':'))
        scheduler.add_job(
            cec_send_command, 'cron',
            args=['standby'],
            day_of_week=day_of_week,
            hour=off_h, minute=off_m,
            id=f'cec_{sched_id}_off',
            replace_existing=True,
            misfire_grace_time=300
        )


schedule_cec_jobs()


# ============ Routes ============

# --- Authentication Routes ---

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Login page"""
    if is_authenticated():
        return redirect(url_for('upload_page'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip().lower()
        password = request.form.get('password', '')

        if verify_user(username, password):
            session['authenticated'] = True
            session['username'] = username
            session.permanent = True
            if has_default_password(username):
                return redirect(url_for('change_password', forced=1))
            return redirect(url_for('upload_page'))

        return render_template('login.html', error='Invalid username or password')

    return render_template('login.html')


@app.route('/logout')
def logout():
    """Logout and clear session"""
    session.clear()
    return redirect(url_for('login'))


@app.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    """Change own password"""
    forced = request.args.get('forced') == '1'
    username = session.get('username')

    if request.method == 'POST':
        forced = request.form.get('forced') == '1'
        new_password = request.form.get('new_password', '')
        confirm = request.form.get('confirm', '')

        if not forced:
            current = request.form.get('current', '')
            if not verify_user(username, current):
                return render_template('change_password.html', error='Current password is incorrect',
                                       is_admin=is_admin(), username=username, forced=forced)

        if new_password != confirm:
            return render_template('change_password.html', error='New passwords do not match',
                                   is_admin=is_admin(), username=username, forced=forced)

        success, message = change_user_password(username, new_password)
        if success:
            if forced:
                return redirect(url_for('upload_page'))
            return render_template('change_password.html', success=message,
                                   is_admin=is_admin(), username=username, forced=False)
        return render_template('change_password.html', error=message,
                               is_admin=is_admin(), username=username, forced=forced)

    return render_template('change_password.html', is_admin=is_admin(),
                           username=username, forced=forced)


# --- Admin Routes ---

@app.route('/admin/users')
@admin_required
def admin_users():
    """User management page"""
    users = load_users()
    user_list = [
        {'username': u, 'role': d['role'], 'created': d.get('created', 'Unknown')}
        for u, d in users.items()
    ]
    return render_template('admin_users.html', users=user_list, is_admin=True, username=session.get('username'))


@app.route('/api/admin/users', methods=['POST'])
@api_admin_required
def api_create_user():
    """Create a new user"""
    data = request.json
    username = data.get('username', '').strip().lower()
    password = data.get('password', '')
    role = data.get('role', 'user')

    success, message = create_user(username, password, role)
    if success:
        return jsonify({'success': True, 'message': message})
    return jsonify({'error': message}), 400


@app.route('/api/admin/users/<username>', methods=['DELETE'])
@api_admin_required
def api_delete_user(username):
    """Delete a user"""
    success, message = delete_user(username)
    if success:
        return jsonify({'success': True, 'message': message})
    return jsonify({'error': message}), 400


@app.route('/api/admin/users/<username>/password', methods=['POST'])
@api_admin_required
def api_reset_password(username):
    """Reset a user's password (admin only)"""
    data = request.json
    new_password = data.get('password', '')

    success, message = change_user_password(username, new_password)
    if success:
        return jsonify({'success': True, 'message': message})
    return jsonify({'error': message}), 400


# --- Main Routes ---

@app.route('/')
def index():
    """Redirect to upload page"""
    return redirect(url_for('upload_page'))


@app.route('/upload')
@login_required
def upload_page():
    """Render the upload interface"""
    settings = load_settings()
    return render_template('upload.html',
                          settings=settings,
                          is_admin=is_admin(),
                          username=session.get('username'),
                          password_changed=not has_default_password(session.get('username')))


@app.route('/gallery')
@login_required
def gallery_page():
    """Redirect to combined upload/gallery page"""
    return redirect(url_for('upload_page'))


@app.route('/display')
def display_page():
    """Render the TV display page"""
    # Allow access if:
    # 1. Request is from localhost (the Pi itself)
    # 2. Valid token is provided
    # 3. User is authenticated via session

    is_localhost = request.remote_addr in ['127.0.0.1', '::1']
    token = request.args.get('token', '')
    valid_token = token == DISPLAY_TOKEN

    if is_localhost or valid_token or is_authenticated():
        settings = load_settings()
        return render_template('display.html', settings=settings)

    return redirect(url_for('login'))


# --- API Routes ---

@app.route('/api/upload', methods=['POST'])
@api_login_required
def api_upload():
    """Handle image uploads"""
    if 'files' not in request.files:
        return jsonify({'error': 'No files provided'}), 400

    files = request.files.getlist('files')
    uploaded = []
    errors = []

    username = session.get('username', 'unknown')

    for file in files:
        if file.filename == '':
            continue

        if file and allowed_file(file.filename):
            ext = file.filename.rsplit('.', 1)[1].lower()
            unique_name = f"{uuid.uuid4().hex[:8]}_{secure_filename(file.filename)}"
            filepath = UPLOAD_FOLDER / unique_name
            file.save(filepath)
            uploaded.append(unique_name)

            # Extract image dimensions (after applying EXIF rotation)
            width, height = None, None
            try:
                with Image.open(filepath) as img:
                    oriented = ImageOps.exif_transpose(img)
                    width, height = oriented.size
            except Exception:
                pass

            # Compute perceptual hash for duplicate detection
            phash = compute_phash(filepath)

            # Add metadata
            update_image_metadata(unique_name,
                enabled=True,
                title='',
                uploaded_at=datetime.now().isoformat(),
                uploaded_by=username,
                width=width,
                height=height,
                phash=phash
            )
        else:
            errors.append(f"Invalid file type: {file.filename}")

    return jsonify({
        'uploaded': uploaded,
        'errors': errors,
        'total_images': len(get_uploaded_images())
    })


@app.route('/api/check-duplicates', methods=['POST'])
@api_login_required
def api_check_duplicates():
    """Check uploaded files for perceptual duplicates against existing gallery.

    Returns duplicate matches and dimension info per file so the client
    can present warnings before the actual upload.
    """
    if 'files' not in request.files:
        return jsonify({'error': 'No files provided'}), 400

    threshold = int(request.args.get('threshold', 10))
    files = request.files.getlist('files')
    gallery = load_gallery()

    results = {}

    for file in files:
        if file.filename == '' or not allowed_file(file.filename):
            continue

        # Save to temp file to compute hash and dimensions
        with tempfile.NamedTemporaryFile(delete=False, suffix='.tmp') as tmp:
            file.save(tmp.name)
            tmp_path = tmp.name

        try:
            new_hash_str = compute_phash(tmp_path)

            # Extract dimensions
            width, height = None, None
            try:
                with Image.open(tmp_path) as img:
                    oriented = ImageOps.exif_transpose(img)
                    width, height = oriented.size
            except Exception:
                pass

            matches = []
            if new_hash_str:
                new_hash = imagehash.hex_to_hash(new_hash_str)
                for existing_fname, meta in gallery.get('images', {}).items():
                    existing_hash = meta.get('phash')
                    if not existing_hash:
                        continue
                    distance = int(new_hash - imagehash.hex_to_hash(existing_hash))
                    if distance <= threshold:
                        matches.append({
                            'filename': existing_fname,
                            'distance': distance,
                            'uploaded_by': meta.get('uploaded_by', '')
                        })
                matches.sort(key=lambda m: m['distance'])

            results[file.filename] = {
                'phash': new_hash_str,
                'width': width,
                'height': height,
                'matches': matches
            }
        finally:
            os.unlink(tmp_path)

    return jsonify({'results': results})


@app.route('/api/gallery/backfill-hashes', methods=['POST'])
@api_admin_required
def api_backfill_hashes():
    """Compute and store perceptual hashes for images that don't have one."""
    gallery = load_gallery()
    updated = 0

    for filename, meta in gallery['images'].items():
        if meta.get('phash'):
            continue
        filepath = UPLOAD_FOLDER / filename
        if not filepath.exists():
            continue
        phash = compute_phash(filepath)
        if phash:
            meta['phash'] = phash
            updated += 1

    save_gallery(gallery)
    return jsonify({'success': True, 'updated': updated})


@app.route('/api/images', methods=['GET'])
def api_get_images():
    """Get slides for display (singles + groups)"""
    settings = load_settings()
    gallery = load_gallery()
    all_images = get_enabled_images()
    groups = gallery.get('groups', {})

    # Build lookup of image metadata by filename
    img_lookup = {}
    for img in all_images:
        img_lookup[img['filename']] = {
            'filename': img['filename'],
            'width': img.get('width'),
            'height': img.get('height'),
            'mat_color': img.get('mat_color'),
            'scale': img.get('scale', 1.0)
        }

    # Find which filenames are in groups
    grouped_filenames = set()
    for group in groups.values():
        grouped_filenames.update(group.get('images', []))

    # Build slides: groups first as encountered, then ungrouped singles
    slides = []

    # Add group slides (only if all images are enabled)
    for group_id, group in groups.items():
        group_images = []
        all_enabled = True
        scales = group.get('scales', {})
        for fname in group.get('images', []):
            if fname in img_lookup:
                img_entry = dict(img_lookup[fname])
                img_entry['scale'] = scales.get(fname, 1.0)
                group_images.append(img_entry)
            else:
                all_enabled = False
        if all_enabled and len(group_images) >= 2:
            slides.append({
                'type': 'group',
                'group_id': group_id,
                'images': group_images,
                'mat_color': group.get('mat_color')
            })

    # Add ungrouped singles
    for img in all_images:
        if img['filename'] not in grouped_filenames:
            slides.append({
                'type': 'single',
                'images': [img_lookup[img['filename']]],
                'mat_color': img.get('mat_color')
            })

    # Backwards compatible: also return flat image list
    filenames = [img['filename'] for img in all_images]

    return jsonify({
        'images': filenames,
        'slides': slides,
        'settings': settings
    })


@app.route('/api/gallery', methods=['GET'])
@api_login_required
def api_get_gallery():
    """Get all images with full metadata for gallery management"""
    images = get_uploaded_images()
    gallery = load_gallery()
    return jsonify({'images': images, 'groups': gallery.get('groups', {})})


@app.route('/api/gallery/<filename>', methods=['PATCH'])
@api_login_required
def api_update_image(filename):
    """Update image metadata"""
    filepath = UPLOAD_FOLDER / secure_filename(filename)
    if not filepath.exists():
        return jsonify({'error': 'Image not found'}), 404

    data = request.json
    allowed_fields = ['enabled', 'title', 'mat_color', 'scale']
    updates = {k: v for k, v in data.items() if k in allowed_fields}

    update_image_metadata(filename, **updates)
    return jsonify({'success': True})


@app.route('/api/gallery/<filename>', methods=['DELETE'])
@api_login_required
def api_delete_image(filename):
    """Delete an image"""
    filepath = UPLOAD_FOLDER / secure_filename(filename)

    if filepath.exists():
        filepath.unlink()
        remove_image_metadata(filename)
        remove_filename_from_groups(filename)
        return jsonify({'success': True})

    return jsonify({'error': 'File not found'}), 404


@app.route('/api/gallery/bulk', methods=['POST'])
@api_login_required
def api_bulk_action():
    """Perform bulk actions on images"""
    data = request.json
    action = data.get('action')
    filenames = data.get('filenames', [])

    if not filenames:
        return jsonify({'error': 'No images selected'}), 400

    if action == 'enable':
        for f in filenames:
            update_image_metadata(f, enabled=True)
        return jsonify({'success': True, 'message': f'Enabled {len(filenames)} images'})

    elif action == 'disable':
        for f in filenames:
            update_image_metadata(f, enabled=False)
        return jsonify({'success': True, 'message': f'Disabled {len(filenames)} images'})

    elif action == 'delete':
        deleted = 0
        for f in filenames:
            filepath = UPLOAD_FOLDER / secure_filename(f)
            if filepath.exists():
                filepath.unlink()
                remove_image_metadata(f)
                remove_filename_from_groups(f)
                deleted += 1
        return jsonify({'success': True, 'message': f'Deleted {deleted} images'})

    return jsonify({'error': 'Invalid action'}), 400


# --- Group API Routes ---

@app.route('/api/groups', methods=['GET'])
@api_login_required
def api_get_groups():
    """Get all groups"""
    gallery = load_gallery()
    return jsonify({'groups': gallery.get('groups', {})})


@app.route('/api/groups', methods=['POST'])
@api_login_required
def api_create_group():
    """Create a new group from selected images"""
    data = request.json
    filenames = data.get('images', [])
    mat_color = data.get('mat_color')

    if len(filenames) < 2:
        return jsonify({'error': 'A group needs at least 2 images'}), 400

    gallery = load_gallery()
    group_id = f"group_{uuid.uuid4().hex[:8]}"
    gallery['groups'][group_id] = {
        'images': filenames,
        'mat_color': mat_color,
        'created_at': datetime.now().isoformat()
    }
    save_gallery(gallery)

    return jsonify({'success': True, 'group_id': group_id})


@app.route('/api/groups/<group_id>', methods=['PATCH'])
@api_login_required
def api_update_group(group_id):
    """Update a group (mat_color, images)"""
    gallery = load_gallery()
    if group_id not in gallery.get('groups', {}):
        return jsonify({'error': 'Group not found'}), 404

    data = request.json
    if 'mat_color' in data:
        gallery['groups'][group_id]['mat_color'] = data['mat_color']
    if 'images' in data:
        if len(data['images']) < 2:
            return jsonify({'error': 'A group needs at least 2 images'}), 400
        gallery['groups'][group_id]['images'] = data['images']
    if 'scales' in data:
        gallery['groups'][group_id]['scales'] = data['scales']

    save_gallery(gallery)
    return jsonify({'success': True})


@app.route('/api/groups/<group_id>', methods=['DELETE'])
@api_login_required
def api_delete_group(group_id):
    """Delete a group (ungroup images, they become individual)"""
    gallery = load_gallery()
    if group_id not in gallery.get('groups', {}):
        return jsonify({'error': 'Group not found'}), 404

    del gallery['groups'][group_id]
    save_gallery(gallery)
    return jsonify({'success': True})


@app.route('/api/settings', methods=['GET', 'POST'])
def api_settings():
    """Get or update settings"""
    if request.method == 'GET':
        return jsonify(load_settings())

    if not is_authenticated():
        return jsonify({'error': 'Authentication required'}), 401

    settings = load_settings()
    data = request.json

    allowed_fields = ['mat_color', 'slideshow_interval', 'transition_duration',
                      'fit_mode', 'shuffle', 'image_order',
                      'target_aspect_ratio']
    for field in allowed_fields:
        if field in data:
            settings[field] = data[field]

    save_settings(settings)
    return jsonify(settings)


@app.route('/api/reorder', methods=['POST'])
@api_login_required
def api_reorder():
    """Reorder images"""
    data = request.json
    if 'images' not in data:
        return jsonify({'error': 'No image order provided'}), 400

    settings = load_settings()
    settings['image_order'] = data['images']
    save_settings(settings)

    return jsonify({'success': True})


@app.route('/uploads/<filename>')
def serve_upload(filename):
    """Serve uploaded images (only files tracked in gallery metadata)"""
    gallery = load_gallery()
    if filename not in gallery.get('images', {}):
        return jsonify({'error': 'Not found'}), 404
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


@app.route('/api/display-token')
@api_admin_required
def api_display_token():
    """Get the display token (admin only)"""
    return jsonify({'token': DISPLAY_TOKEN})


# --- Backup Routes ---

@app.route('/backup')
@admin_required
def backup_page():
    """Render the backup settings page"""
    return render_template('backup.html',
                           is_admin=True,
                           username=session.get('username'))


@app.route('/api/backup/status', methods=['GET'])
@api_admin_required
def api_backup_status():
    """Get backup status"""
    configured = is_backup_configured()
    log = load_backup_log()
    backup_settings = get_backup_settings()

    # Get next scheduled run time
    next_run = None
    job = scheduler.get_job('daily_backup')
    if job and job.next_run_time:
        next_run = job.next_run_time.isoformat()

    return jsonify({
        'configured': configured,
        'in_progress': backup_in_progress,
        'restore_in_progress': restore_in_progress,
        'last_backup': log.get('last_backup'),
        'last_result': log.get('last_result'),
        'last_error': log.get('last_error'),
        'next_scheduled': next_run,
        'backup_time': backup_settings['backup_time'],
        'backup_path': backup_settings['backup_path']
    })


@app.route('/api/backup/run', methods=['POST'])
@api_admin_required
def api_backup_run():
    """Trigger a manual backup"""
    if backup_in_progress:
        return jsonify({'error': 'Backup already in progress'}), 409
    if not is_backup_configured():
        return jsonify({'error': 'Backup not configured'}), 400
    run_backup_async()
    return jsonify({'success': True, 'message': 'Backup started'})


@app.route('/api/backup/restore', methods=['POST'])
@api_admin_required
def api_backup_restore():
    """Restore photos and data from Dropbox backup"""
    if backup_in_progress or restore_in_progress:
        return jsonify({'error': 'A backup or restore is already in progress'}), 409
    if not is_backup_configured():
        return jsonify({'error': 'Backup not configured'}), 400
    run_restore_async()
    return jsonify({'success': True, 'message': 'Restore started'})


@app.route('/api/backup/configure', methods=['POST'])
@api_admin_required
def api_backup_configure():
    """Configure Dropbox backup with an rclone token"""
    data = request.json
    token = data.get('token', '').strip()

    if not token:
        return jsonify({'error': 'No token provided'}), 400

    # Validate that the token looks like JSON
    try:
        json.loads(token)
    except json.JSONDecodeError:
        return jsonify({'error': 'Invalid token format. Must be a JSON string from rclone authorize.'}), 400

    # Write rclone config
    generate_rclone_config(token)

    # Test the connection
    try:
        result = subprocess.run(
            ['rclone', 'lsd', 'dropbox:', '--config', str(RCLONE_CONFIG_FILE)],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode != 0:
            # Clean up on failure
            RCLONE_CONFIG_FILE.unlink(missing_ok=True)
            error = result.stderr.strip()[:300]
            return jsonify({'error': f'Connection test failed: {error}'}), 400
    except subprocess.TimeoutExpired:
        RCLONE_CONFIG_FILE.unlink(missing_ok=True)
        return jsonify({'error': 'Connection test timed out'}), 400
    except FileNotFoundError:
        RCLONE_CONFIG_FILE.unlink(missing_ok=True)
        return jsonify({'error': 'rclone is not installed'}), 500

    return jsonify({'success': True, 'message': 'Dropbox connected successfully'})


@app.route('/api/backup/configure', methods=['DELETE'])
@api_admin_required
def api_backup_disconnect():
    """Disconnect Dropbox backup"""
    RCLONE_CONFIG_FILE.unlink(missing_ok=True)
    return jsonify({'success': True, 'message': 'Dropbox disconnected'})


@app.route('/api/backup/history', methods=['GET'])
@api_admin_required
def api_backup_history():
    """Get backup history"""
    log = load_backup_log()
    return jsonify({'history': log.get('history', [])})


@app.route('/api/backup/settings', methods=['POST'])
@api_admin_required
def api_backup_settings():
    """Update backup settings (time, path)"""
    data = request.json
    settings = load_settings()

    if 'backup_time' in data:
        time_str = data['backup_time']
        # Validate HH:MM format
        try:
            h, m = map(int, time_str.split(':'))
            if not (0 <= h <= 23 and 0 <= m <= 59):
                raise ValueError
            settings['backup_time'] = time_str
            reschedule_backup(time_str)
        except (ValueError, AttributeError):
            return jsonify({'error': 'Invalid time format. Use HH:MM'}), 400

    if 'backup_path' in data:
        path = data['backup_path'].strip()
        if path:
            settings['backup_path'] = path

    save_settings(settings)
    return jsonify({'success': True})


# --- CEC TV Control Routes ---

@app.route('/api/cec/status', methods=['GET'])
@api_login_required
def api_cec_status():
    """Check if CEC control is available."""
    return jsonify({'available': is_cec_available()})


@app.route('/api/cec/test', methods=['POST'])
@api_admin_required
def api_cec_test():
    """Test CEC by sending a command to the TV."""
    data = request.json or {}
    command = data.get('command', 'on')
    if command not in ('on', 'standby'):
        return jsonify({'error': 'Invalid command. Use "on" or "standby".'}), 400
    result = cec_send_command(command)
    if result['success']:
        return jsonify({'success': True})
    return jsonify({'error': result.get('error', 'Unknown error')}), 500


@app.route('/api/tv-schedules', methods=['GET'])
@api_login_required
def api_get_tv_schedules():
    """Get all TV schedules."""
    settings = load_settings()
    return jsonify({
        'schedules': settings.get('tv_schedules', []),
        'cec_available': is_cec_available()
    })


@app.route('/api/tv-schedules', methods=['POST'])
@api_admin_required
def api_save_tv_schedules():
    """Save all TV schedules."""
    data = request.json
    schedules = data.get('schedules', [])

    for sched in schedules:
        if 'id' not in sched:
            sched['id'] = f'sched_{uuid.uuid4().hex[:8]}'
        for field in ('on_time', 'off_time'):
            try:
                h, m = map(int, sched[field].split(':'))
                if not (0 <= h <= 23 and 0 <= m <= 59):
                    raise ValueError
            except (ValueError, KeyError, AttributeError):
                return jsonify({'error': f'Invalid {field} format. Use HH:MM.'}), 400
        days = sched.get('days', [])
        if not isinstance(days, list) or not all(isinstance(d, int) and 0 <= d <= 6 for d in days):
            return jsonify({'error': 'Invalid days. Must be array of integers 0-6.'}), 400
        sched.setdefault('enabled', True)

    settings = load_settings()
    settings['tv_schedules'] = schedules
    save_settings(settings)
    schedule_cec_jobs()

    return jsonify({'success': True, 'schedules': schedules})


# ============ Network Info ============

def get_network_info():
    """Get network addresses for display."""
    import socket
    info = {'local_ip': None, 'tailscale_ip': None}
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        info['local_ip'] = s.getsockname()[0]
        s.close()
    except Exception:
        pass
    try:
        result = subprocess.run(['tailscale', 'ip', '-4'],
                                capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            info['tailscale_ip'] = result.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return info


@app.route('/api/network-info', methods=['GET'])
@api_admin_required
def api_network_info():
    """Get network info (local IP, Tailscale IP) for admin display."""
    return jsonify(get_network_info())


# ============ Maintenance Window ============

@app.route('/api/maintenance-window', methods=['GET'])
def api_maintenance_window():
    """Check if current time is within a maintenance window (TV is off)."""
    settings = load_settings()
    schedules = settings.get('tv_schedules', [])

    if not schedules:
        return jsonify({'can_deploy': True, 'reason': 'No TV schedules configured'})

    now = datetime.now()
    current_day = now.weekday()
    current_minutes = now.hour * 60 + now.minute

    for sched in schedules:
        if not sched.get('enabled', True):
            continue
        days = sched.get('days', [])
        if current_day not in days:
            continue

        on_h, on_m = map(int, sched['on_time'].split(':'))
        off_h, off_m = map(int, sched['off_time'].split(':'))
        on_minutes = on_h * 60 + on_m
        off_minutes = off_h * 60 + off_m

        if on_minutes <= current_minutes < off_minutes:
            return jsonify({
                'can_deploy': False,
                'reason': f'TV is scheduled ON until {sched["off_time"]}'
            })

    return jsonify({'can_deploy': True, 'reason': 'Outside TV schedule'})


# ============ Error Handlers ============

@app.errorhandler(413)
def too_large(e):
    return jsonify({'error': 'File too large. Maximum size is 50MB.'}), 413


# ============ Main ============

if __name__ == '__main__':
    # Ensure default admin exists
    load_users()

    print("\n" + "="*50)
    print("Pi Photo Frame Server")
    print("="*50)
    print(f"Upload & Gallery: http://localhost:5000/upload")
    print(f"TV Display:       http://localhost:5000/display")
    print(f"\nDefault login:    admin / password")
    print("="*50 + "\n")

    app.run(host='0.0.0.0', port=5000, debug=os.environ.get('FLASK_DEBUG', '').lower() in ('1', 'true'))
