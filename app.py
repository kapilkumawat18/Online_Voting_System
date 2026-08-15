import eventlet
import eventlet.wsgi
from flask import Flask, render_template, request, redirect, jsonify, url_for, session , flash , send_from_directory,get_flashed_messages
from flask_mysqldb import MySQL
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from werkzeug.middleware.proxy_fix import ProxyFix
from datetime import datetime , date
import secrets
import hashlib
import io
import re
import requests
import MySQLdb.cursors
from flask_caching import Cache
import os , time
from dotenv import load_dotenv
from flask_socketio import SocketIO
from functools import wraps
from flask_wtf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

load_dotenv("otp.env")

# Initialize the Flask application
app = Flask(__name__)
# Render terminates TLS at its proxy; trust the standard forwarded headers so
# request.is_secure and HTTPS-aware security behavior work correctly.
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
socketio = SocketIO(app)
app.secret_key = os.getenv('FLASK_SECRET_KEY')
if not app.secret_key:
    app.secret_key = secrets.token_hex(32)
    print("WARNING: FLASK_SECRET_KEY is not set; sessions will reset on restart.")

@app.before_request
def log_request():
    print(f"REQUEST: {request.method} {request.path}", flush=True)

app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = (
    os.getenv('RENDER', '').lower() in ('1', 'true', 'yes')
    or os.getenv('FORCE_HTTPS_COOKIES', 'false').lower() == 'true'
)

csrf = CSRFProtect(app)
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["300 per minute"],
    storage_uri="memory://"
)

# Cache config (simple in-memory, fast)
cache = Cache(app, config={'CACHE_TYPE': 'SimpleCache', 'CACHE_DEFAULT_TIMEOUT': 60})

# MySQL configurations — pulled from otp.env instead of hardcoded in source
app.config['MYSQL_HOST'] = os.getenv('MYSQL_HOST', 'localhost')
app.config['MYSQL_PORT'] = int(os.getenv('MYSQL_PORT', 3306))
app.config['MYSQL_USER'] = os.getenv('MYSQL_USER', 'root')
app.config['MYSQL_PASSWORD'] = os.getenv('MYSQL_PASSWORD')
app.config['MYSQL_DB'] = os.getenv('MYSQL_DB', 'online_voting')
app.config['MYSQL_DATABASE_CHARSET'] = 'utf8mb4'

# Optional TLS for hosted MySQL providers that require it (e.g. Aiven's free tier).
# Leave MYSQL_SSL_CA unset for local MySQL — no SSL config is applied by default.
_mysql_ssl_ca = os.getenv('MYSQL_SSL_CA')
if _mysql_ssl_ca:
    app.config['MYSQL_CUSTOM_OPTIONS'] = {'ssl': {'ca': _mysql_ssl_ca}}

mysql = MySQL(app)


def init_db():
    """Create every table the app needs if they don't already exist yet.
    Runs once at startup — safe to call against a fresh, empty database
    (e.g. right after a new Railway/Render MySQL instance is provisioned)."""
    statements = [
        """
        CREATE TABLE IF NOT EXISTS users (
            id INT AUTO_INCREMENT PRIMARY KEY,
            role VARCHAR(10) NOT NULL,
            name VARCHAR(100) NOT NULL,
            email VARCHAR(150) NOT NULL UNIQUE,
            voterId VARCHAR(50) NOT NULL UNIQUE,
            password VARCHAR(255) NOT NULL,
            dark_mode BOOLEAN NOT NULL DEFAULT FALSE,
            profile_pic VARCHAR(255) DEFAULT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """,
        """
        CREATE TABLE IF NOT EXISTS elections (
            id INT AUTO_INCREMENT PRIMARY KEY,
            title VARCHAR(150) NOT NULL,
            description TEXT,
            status VARCHAR(20) NOT NULL,
            start_date DATE NOT NULL,
            end_date DATE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """,
        """
        CREATE TABLE IF NOT EXISTS candidates (
            id INT AUTO_INCREMENT PRIMARY KEY,
            election_id INT NOT NULL,
            voterId VARCHAR(50) NOT NULL,
            name VARCHAR(100) NOT NULL,
            FOREIGN KEY (election_id) REFERENCES elections(id) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """,
        """
        CREATE TABLE IF NOT EXISTS votes (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            candidate_id INT NOT NULL,
            election_id INT NOT NULL,
            voted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE KEY unique_user_election (user_id, election_id),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (candidate_id) REFERENCES candidates(id) ON DELETE CASCADE,
            FOREIGN KEY (election_id) REFERENCES elections(id) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """,
        """
        CREATE TABLE IF NOT EXISTS notifications (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            message VARCHAR(255) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """,
    ]
    with app.app_context():
        cur = None
        try:
            cur = mysql.connection.cursor()
            for statement in statements:
                cur.execute(statement)
            mysql.connection.commit()
            print("Database ready — tables verified/created.")
        except Exception as e:
            print("init_db() error (check MYSQL_* env vars / DB reachability):", e)
        finally:
            if cur:
                cur.close()


init_db()


# ----------------- Auth helpers -----------------
def login_required(f):
    """Redirect anonymous visitors to the login page, remembering where they were headed."""
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get('logged_in'):
            return redirect(url_for('login', next=request.path))
        return f(*args, **kwargs)
    return wrapper


def admin_required(f):
    """Redirect anyone who isn't a logged-in admin to the login page."""
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get('logged_in') or session.get('role') != 'admin':
            return redirect(url_for('login', next=request.path))
        return f(*args, **kwargs)
    return wrapper


def is_safe_next_url(next_url):
    """Only ever redirect back to a same-site, relative path after login.

    The previous check was `next_url.startswith('/')`, which looks safe but
    isn't: a value like `//evil.com/phish` or `/\\evil.com` also starts with
    '/' and is treated by browsers as a *protocol-relative external URL* —
    so the login page could be used to bounce a victim straight to a
    phishing site right after they type in their password. That pattern is
    exactly what Google Safe Browsing's "tries to trick visitors" detector
    looks for on a page that collects credentials.
    """
    if not next_url:
        return False
    if not next_url.startswith('/'):
        return False
    if next_url.startswith('//') or next_url.startswith('/\\'):
        return False
    # Reject anything that parses out an external netloc/scheme at all.
    from urllib.parse import urlparse
    parsed = urlparse(next_url)
    return not parsed.netloc and not parsed.scheme


def get_dark_mode():
    """Resolve the current visitor's dark-mode preference (DB lookup only when logged in)."""
    user_id = session.get('user_id')
    dark_mode = session.get('dark_mode', False)  # Default to session / anonymous default

    if user_id:
        cursor = None
        try:
            cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
            cursor.execute("SELECT dark_mode FROM users WHERE id = %s", (user_id,))
            row = cursor.fetchone()
            if row:
                dark_mode = bool(row.get('dark_mode', False))
        except Exception as e:
            print("get_dark_mode() DB error:", e)  # Safe logging
        finally:
            if cursor:
                cursor.close()

    session['dark_mode'] = dark_mode
    return dark_mode


@app.route('/')
def index():
    """Public landing page — no login required. Buttons that need an account send
    the visitor to /login instead of gating the whole homepage behind it."""
    return render_template('home.html', dark_mode=get_dark_mode())


@app.route('/get_dark_mode_status')
def get_dark_mode_status():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'dark_mode': False})

    cursor = None
    try:
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute("SELECT dark_mode FROM users WHERE id = %s", (user_id,))
        row = cursor.fetchone()
        dark_mode = bool(row.get('dark_mode')) if row else False
        return jsonify({'dark_mode': dark_mode})
    except Exception as e:
        print("get_dark_mode_status() DB error:", e)
        return jsonify({'dark_mode': False})
    finally:
        if cursor:
            cursor.close()


@app.route('/toggle_dark_mode', methods=['POST'])
def toggle_dark_mode():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'status': 'error', 'message': 'User not logged in'}), 401

    data = request.get_json(silent=True) or {}
    dark_mode = bool(data.get('dark_mode', False))

    cursor = None
    try:
        cursor = mysql.connection.cursor()
        cursor.execute("UPDATE users SET dark_mode = %s WHERE id = %s", (dark_mode, user_id))
        mysql.connection.commit()
    except Exception as e:
        try:
            mysql.connection.rollback()
        except Exception:
            pass
        print("toggle_dark_mode() DB error:", e)
        return jsonify({'status': 'error', 'message': 'Database error'}), 500
    finally:
        if cursor:
            cursor.close()

    session['dark_mode'] = dark_mode
    return jsonify({'status': 'success', 'dark_mode': dark_mode})


# For voting page
@app.route('/Voting')
@login_required
def Voting():
    if session.get('role') == 'voter':
        return render_template('Voting.html')
    return render_template('adminvote.html')


@app.route('/adminvote')
@admin_required
def adminvote():
    return render_template('adminvote.html')


@app.route('/electionform')
@admin_required
def electionform():
    return render_template('electionform.html')


@app.route('/adminresults')
@admin_required
def adminresults():
    return render_template('adminresults.html')


@app.route('/admin')
@admin_required
def admin():
    return render_template('admin.html')


# ✅ Cache headers — only for real static assets. Applying this to every response
# (including JSON endpoints and redirects, as before) made notifications, dark-mode
# toggling, and login redirects appear to "stick"/lag for up to an hour.
#
# This also sets the security headers Chrome/Safe Browsing and any manual
# security review will check for: nosniff stops the browser from ever
# re-interpreting an uploaded "photo" as HTML/JS, X-Frame-Options/CSP
# frame-ancestors stop the login/OTP pages from being framed for
# clickjacking, and Referrer-Policy keeps voter emails/tokens out of
# outbound Referer headers.
@app.after_request
def add_header(response):
    if request.path.startswith('/static/') or request.path.startswith('/uploads/'):
        response.headers["Cache-Control"] = "public, max-age=3600"
    else:
        response.headers["Cache-Control"] = "no-store"

    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    # NOTE: templates use inline onclick="" handlers and inline <script> blocks
    # throughout (login.html, electionform.html, etc.), so script-src needs
    # 'unsafe-inline' to avoid silently breaking those — removing it is a real
    # improvement but requires migrating every onclick handler to
    # addEventListener + a nonce first. What this CSP still buys us: the
    # browser will never load a script, iframe, or media file from anywhere
    # other than this origin, so injected/foreign-domain content (the pattern
    # Safe Browsing flags as "trick visitors into downloading software") is
    # blocked even if an XSS bug is later found.
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "img-src 'self' data:; "
        "media-src 'self'; "
        "script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline'; "
        "frame-src 'none'; "
        "frame-ancestors 'none'; "
        "object-src 'none'; "
        "base-uri 'self'; "
        "form-action 'self'"
    )
    if request.is_secure:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


@app.route('/home')
def home():
    # Logged-in voters land here after login; anonymous visitors are sent to /login.
    # (Not cached — the page renders the visitor's own name/role via the header, so a
    # shared cache would have leaked one user's session details to the next visitor.)
    if not session.get('logged_in') or session.get('role') != 'voter':
        return redirect(url_for('login', next=request.path))
    return render_template('home.html', dark_mode=get_dark_mode())


@app.route('/uploads/profiles/<path:filename>')
@login_required
def uploaded_file(filename):
    return send_from_directory('static/uploads/profiles', filename)
# Notification Table
def add_notification(user_id, message):
    if not user_id or not message:
        return  # Skip invalid inputs

    cur = None
    try:
        cur = mysql.connection.cursor()

        # Insert new notification
        cur.execute(
            "INSERT INTO notifications (user_id, message) VALUES (%s, %s)",
            (user_id, message)
        )

        # Trim to the most recent 20 in one round trip instead of fetching every
        # row for this user into Python and deleting one-at-a-time.
        cur.execute(
            """
            DELETE FROM notifications
            WHERE user_id = %s AND id NOT IN (
                SELECT id FROM (
                    SELECT id FROM notifications
                    WHERE user_id = %s
                    ORDER BY id DESC
                    LIMIT 20
                ) keep
            )
            """,
            (user_id, user_id)
        )
        mysql.connection.commit()

        # Emit notification to frontend
        socketio.emit('new_notification', {'message': message, 'user_id': user_id})

    except Exception as e:
        print("Error adding notification:", str(e))
        try:
            mysql.connection.rollback()
        except Exception:
            pass
    finally:
        if cur:
            cur.close()


def add_notification_to_all_users(message):
    """Bulk-notify every user in one insert instead of looping add_notification()
    per user (each of which was its own INSERT + commit + trim query). This is
    what made /voting slow — it ran the per-user loop on every page load whenever
    an election had just started/ended/was about to start."""
    cur = None
    try:
        cur = mysql.connection.cursor()
        cur.execute("SELECT id FROM users")
        user_ids = [row[0] for row in cur.fetchall()]
        if not user_ids:
            return

        cur.executemany(
            "INSERT INTO notifications (user_id, message) VALUES (%s, %s)",
            [(uid, message) for uid in user_ids]
        )

        # Trim every affected user back down to their most recent 20 in one query
        # (requires MySQL 8+ for window functions).
        cur.execute(
            """
            DELETE FROM notifications WHERE id IN (
                SELECT id FROM (
                    SELECT id, ROW_NUMBER() OVER (
                        PARTITION BY user_id ORDER BY id DESC
                    ) AS rn
                    FROM notifications
                    WHERE user_id IN %s
                ) ranked
                WHERE rn > 20
            )
            """,
            (tuple(user_ids),)
        )
        mysql.connection.commit()

        for uid in user_ids:
            socketio.emit('new_notification', {'message': message, 'user_id': uid})

    except Exception as e:
        print("Error bulk-adding notifications:", str(e))
        try:
            mysql.connection.rollback()
        except Exception:
            pass
    finally:
        if cur:
            cur.close()


@app.route('/get_notifications', methods=['GET'])
def get_notifications():
    # Previously trusted a `user_id` query parameter straight from the
    # client — anyone logged in (or not) could read anyone else's
    # notifications just by changing the number in the URL. Notifications
    # are always for the current session's own user now.
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({"notifications": []})

    cur = None
    try:
        cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cur.execute(
            "SELECT id, message, created_at FROM notifications "
            "WHERE user_id = %s ORDER BY created_at DESC",
            (user_id,)
        )
        notifications = cur.fetchall()

        # Convert datetime → string
        for notif in notifications:
            if notif.get("created_at"):
                notif["created_at"] = notif["created_at"].strftime('%Y-%m-%d %H:%M:%S')

        return jsonify({"notifications": notifications})
    except Exception as e:
        print("Error fetching notifications:", str(e))
        return jsonify({"error": "Error fetching notifications"}), 500
    finally:
        if cur:
            cur.close()


@app.route('/remove_notification/<int:notif_id>', methods=['POST'])
def remove_notification(notif_id):
    # Previously deleted by ID alone with no ownership check and no login
    # requirement — any visitor could delete any user's notifications just
    # by guessing/incrementing the numeric ID. Scoped to the owning user now.
    if not session.get('user_id'):
        return jsonify({"status": "error", "message": "Unauthorized"}), 401

    cur = None
    try:
        cur = mysql.connection.cursor()
        cur.execute(
            "DELETE FROM notifications WHERE id = %s AND user_id = %s",
            (notif_id, session['user_id'])
        )
        mysql.connection.commit()
        return jsonify({"status": "success"})
    except Exception as e:
        print("Error removing notification:", str(e))
        try:
            mysql.connection.rollback()
        except Exception:
            pass
        return jsonify({"status": "error", "message": "Failed to remove notification"}), 500
    finally:
        if cur:
            cur.close()


@app.route('/notifications')
def notifications_page():
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('login'))

    cur = None
    try:
        cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cur.execute(
            "SELECT id, message, created_at FROM notifications "
            "WHERE user_id = %s ORDER BY created_at DESC",
            (user_id,)
        )
        notifications = cur.fetchall()
        return render_template('notifications.html', notifications=notifications)
    except Exception as e:
        print("Error fetching notifications page:", str(e))
        return jsonify({"error": "Error fetching notifications"}), 500
    finally:
        if cur:
            cur.close()


@app.route('/login', methods=['GET', 'POST'])
@limiter.limit("10 per minute", methods=["POST"])
def login():
    # GET → show the login/register page. This is the page "necessary buttons"
    # (Vote, Home dashboard, Records, etc.) redirect to when a visitor isn't logged in.
    if request.method == 'GET':
        if session.get('logged_in'):
            return redirect(url_for('admin' if session.get('role') == 'admin' else 'home'))
        return render_template('login.html', next=request.args.get('next', ''))

    # The login role is selected by the user, then verified against the
    # role stored in the database. Never hard-code every login as voter.
    role = (request.form.get('role') or 'voter').strip().lower()
    if role not in ('voter', 'admin'):
        flash("Invalid account role.", "login_error")
        return redirect(url_for('login'))

    name = request.form.get('name', '').strip()
    username = request.form.get('username')
    password = request.form.get('password')

    if not role or not name or not username or not password:
        flash("Please fill all fields.", "login_error")
        return redirect(url_for('login'))

    cur = None
    try:
        cur = mysql.connection.cursor()
        query = "SELECT id, name, email, password, dark_mode FROM users WHERE name=%s AND LOWER(email)=LOWER(%s) AND role=%s LIMIT 1"
        cur.execute(query, (name, username.strip(), role))
        user = cur.fetchone()

        if not user:
            flash("Invalid login credentials, please try again.", "login_error")
            return redirect(url_for('login'))

        user_id, db_name, db_email, hashed_password, dark_mode = user

        if check_password_hash(hashed_password, password):
            # Store session data
            session.update({
                'logged_in': True,
                'user_id': user_id,
                'name': db_name,
                'username': db_email,
                'role': role,
                'dark_mode': dark_mode,
            })

            flash("Login successful!", "login_success")
            add_notification(user_id, "You have successfully logged in.")

            next_url = request.form.get('next') or request.args.get('next')
            if is_safe_next_url(next_url):
                return redirect(next_url)
            return redirect(url_for('admin' if role == 'admin' else 'home'))
        else:
            flash("Incorrect password, please try again.", "login_error")
            return redirect(url_for('login'))

    except Exception as e:
        print("Login error:", str(e))
        flash("Internal server error.", "login_error")
        return redirect(url_for('login'))
    finally:
        if cur:
            cur.close()

@app.route('/register', methods=['POST'])
@limiter.limit("5 per minute")
def register():
    role = request.form.get('role')
    name = request.form.get('name')
    email = request.form.get('email')
    voterId = request.form.get('voterId')
    password = request.form.get('password')

    if not all([role, name, email, voterId, password]):
        flash("All fields are required.", "login_error")
        return redirect(url_for('login'))

    # The email OTP is otherwise decorative — without this check, anyone
    # could submit the registration form directly (skipping /send_otp and
    # /verify_otp entirely) and register with an email they don't own.
    if session.get("register_email_verified") != email:
        flash("Please verify your email with the OTP before registering.", "login_error")
        return redirect(url_for('login'))

    if len(password) < 8:
        flash("Password must be at least 8 characters.", "login_error")
        return redirect(url_for('login'))

    hashed_password = generate_password_hash(password)
    cur = None
    try:
        cur = mysql.connection.cursor()

        # Check duplicates (email or voterId) in one query for speed
        cur.execute("SELECT id, email, voterId FROM users WHERE email = %s OR voterId = %s", (email, voterId))
        existing = cur.fetchone()
        if existing:
            if existing[1] == email:
                flash("Error: This email is already registered.", "login_error")
            elif existing[2] == voterId:
                flash("Error: This Voter ID is already registered.", "login_error")
            return redirect(url_for('login'))

        # Insert user
        cur.execute(
            "INSERT INTO users (role, name, email, voterId, password, dark_mode) VALUES (%s, %s, %s, %s, %s, %s)",
            (role, name, email, voterId, hashed_password, False),
        )
        mysql.connection.commit()

        user_id = cur.lastrowid  # Faster than querying again
        if user_id:
            add_notification(user_id, "You have successfully registered on Secure Vote.")

        session.pop("register_email_verified", None)
        flash("Registration successful! Please login.", "login_success")
        return redirect(url_for('login'))

    except Exception as e:
        print("Register error:", str(e))
        mysql.connection.rollback()
        flash("Internal server error. Please try again.", "login_error")
        return redirect(url_for('login'))
    finally:
        if cur:
            cur.close()


# ----------------- Email (transactional API, not SMTP) -----------------
# Render's default outbound networking blocks arbitrary TCP egress on the
# ports SMTP needs (25/465/587) on most plans — that's the direct cause of
# "Error sending email: [Errno 101] Network is unreachable" in the logs.
# Flask-Mail/Gmail SMTP simply cannot work there. The fix is to send mail
# over HTTPS (port 443, always open) via a transactional email provider's
# REST API instead. This uses Brevo (formerly Sendinblue) — free tier is
# generous and the API is a single POST. Swapping providers later only
# means rewriting send_email_via_api(); nothing else in the app changes.
#
# Required environment variables (set these in Render → Environment, and in
# otp.env locally — never commit real values):
#   BREVO_API_KEY      - API key from Brevo → Settings → SMTP & API
#   BREVO_SENDER_EMAIL - the "from" address; must be a verified sender in Brevo
#   BREVO_SENDER_NAME  - optional, defaults to "Secure Vote"
BREVO_API_KEY = os.getenv("BREVO_API_KEY")
BREVO_SENDER_EMAIL = os.getenv("BREVO_SENDER_EMAIL")
BREVO_SENDER_NAME = os.getenv("BREVO_SENDER_NAME", "Secure Vote")
BREVO_API_URL = "https://api.brevo.com/v3/smtp/email"


def send_email_via_api(to_email, subject, body_text):
    """Send an email through Brevo's HTTP API. Returns (ok, user_facing_message).

    Never raises — every failure mode (missing config, timeout, non-2xx
    response, network error) is caught and turned into a generic message,
    and full detail is only ever printed server-side, never returned to the
    client or logged with the OTP value itself.
    """
    if not BREVO_API_KEY or not BREVO_SENDER_EMAIL:
        print("send_email_via_api: BREVO_API_KEY / BREVO_SENDER_EMAIL not configured.")
        return False, "Email service is not configured. Please contact support."

    payload = {
        "sender": {"name": BREVO_SENDER_NAME, "email": BREVO_SENDER_EMAIL},
        "to": [{"email": to_email}],
        "subject": subject,
        "textContent": body_text,
    }
    headers = {
        "accept": "application/json",
        "api-key": BREVO_API_KEY,
        "content-type": "application/json",
    }
    try:
        resp = requests.post(BREVO_API_URL, json=payload, headers=headers, timeout=10)
        if resp.status_code in (200, 201):
            return True, "OTP sent successfully!"
        print(f"send_email_via_api: provider returned {resp.status_code}")
        return False, "We couldn't send the email right now. Please try again shortly."
    except requests.exceptions.Timeout:
        print("send_email_via_api: request timed out")
        return False, "Email service timed out. Please try again."
    except requests.exceptions.RequestException as e:
        print(f"send_email_via_api: network error: {type(e).__name__}")
        return False, "Email service is temporarily unavailable. Please try again."


# ----------------- OTP Helpers -----------------
# OTP_RESEND_COOLDOWN and OTP_TTL are enforced server-side — the 120s cooldown
# button in login.html is only a UX nicety, it was never actually enforced by
# the backend, so anyone calling /send_otp directly could request unlimited
# OTPs. OTP_MAX_ATTEMPTS caps brute-force guesses against a single OTP
# (6-digit codes are only ~1M possibilities, so unlimited guessing is not
# acceptable — Flask-Limiter below adds a second, IP-based layer on top).
OTP_TTL_SECONDS = 300          # 5 minutes
OTP_RESEND_COOLDOWN = 60       # seconds between sends for the same purpose
OTP_MAX_ATTEMPTS = 5           # wrong guesses allowed before the OTP is invalidated
RESET_VERIFIED_TTL = 600       # window to actually reset the password after OTP success


def _hash_otp(otp, email, purpose):
    # Salted with the app secret key so a stolen session cookie value alone
    # (already signed, but defense in depth) can't be replayed against a
    # different email/purpose, and the raw 6-digit code is never held in the
    # session in plaintext.
    raw = f"{app.secret_key}:{purpose}:{email}:{otp}".encode()
    return hashlib.sha256(raw).hexdigest()


def generate_and_store_otp(purpose, email):
    """Returns (otp_or_None, error_message_or_None). Enforces the resend cooldown."""
    last_sent = session.get(f"{purpose}_last_sent")
    if last_sent and (time.time() - last_sent) < OTP_RESEND_COOLDOWN:
        wait = int(OTP_RESEND_COOLDOWN - (time.time() - last_sent))
        return None, f"Please wait {wait}s before requesting another OTP."

    otp = secrets.randbelow(900000) + 100000  # cryptographically secure 6-digit code
    session[f"{purpose}_otp_hash"] = _hash_otp(otp, email, purpose)
    session[f"{purpose}_email"] = email
    session[f"{purpose}_time"] = time.time()
    session[f"{purpose}_last_sent"] = time.time()
    session[f"{purpose}_attempts"] = 0
    return otp, None


def is_otp_valid(purpose, email, entered_otp):
    otp_hash = session.get(f"{purpose}_otp_hash")
    otp_time = session.get(f"{purpose}_time")
    stored_email = session.get(f"{purpose}_email")

    if not otp_hash or not otp_time or not stored_email:
        return False, "No OTP found. Please request a new one."

    if not email or email.strip().lower() != str(stored_email).strip().lower():
        return False, "OTP request does not match this email."

    if time.time() - otp_time > OTP_TTL_SECONDS:
        _clear_otp_session(purpose)
        return False, "OTP expired. Request a new one."

    attempts = session.get(f"{purpose}_attempts", 0)
    if attempts >= OTP_MAX_ATTEMPTS:
        _clear_otp_session(purpose)
        return False, "Too many incorrect attempts. Please request a new OTP."

    entered_text = str(entered_otp or "").strip()
    if not re.fullmatch(r"\d{6}", entered_text):
        session[f"{purpose}_attempts"] = attempts + 1
        remaining = OTP_MAX_ATTEMPTS - (attempts + 1)
        if remaining <= 0:
            _clear_otp_session(purpose)
            return False, "Too many incorrect attempts. Please request a new OTP."
        return False, f"Invalid OTP. {remaining} attempt(s) remaining."

    expected_hash = _hash_otp(entered_text, stored_email, purpose)
    if secrets.compare_digest(expected_hash, otp_hash):
        return True, ""

    session[f"{purpose}_attempts"] = attempts + 1
    remaining = OTP_MAX_ATTEMPTS - (attempts + 1)
    if remaining <= 0:
        _clear_otp_session(purpose)
        return False, "Too many incorrect attempts. Please request a new OTP."
    return False, f"Invalid OTP. {remaining} attempt(s) remaining."


def _clear_otp_session(purpose):
    for suffix in ("otp_hash", "email", "time", "attempts"):
        session.pop(f"{purpose}_{suffix}", None)


# ----------------- OTP Routes -----------------
@app.route("/send_otp", methods=["POST"])
@limiter.limit("5 per minute")
def send_otp():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip()

    if not email or not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        return jsonify({"message": "A valid email is required", "success": False}), 400

    otp, cooldown_error = generate_and_store_otp("register", email)
    if cooldown_error:
        return jsonify({"message": cooldown_error, "success": False}), 429

    email_content = f"""Hi,

Welcome to Secure Vote! You are trying to register for Secure Vote with this email address.

Please enter the OTP {otp} to verify your email address.

The code is valid for 5 minutes.

You can ignore this email if you have not made this request.

Regards,
The Secure Vote Team"""

    ok, message = send_email_via_api(email, "Email Verification OTP", email_content)
    if not ok:
        _clear_otp_session("register")
    return jsonify({"message": message, "success": ok}), (200 if ok else 502)


@app.route("/verify_otp", methods=["POST"])
@limiter.limit("10 per minute")
def verify_otp():
    data = request.get_json(silent=True) or {}
    entered_otp = data.get("otp")
    email = session.get("register_email")

    if not entered_otp:
        return jsonify({"message": "OTP is required", "success": False}), 400
    if not email:
        return jsonify({"message": "No OTP request found. Please request a new OTP.", "success": False}), 400

    valid, error = is_otp_valid("register", email, entered_otp)
    if not valid:
        return jsonify({"message": error, "success": False}), 400

    # Mark this email as verified for the registration step that follows,
    # then clear the OTP itself so it can't be reused (single-use).
    session["register_email_verified"] = email
    _clear_otp_session("register")
    return jsonify({"message": "OTP verified successfully!", "success": True})


@app.route("/send_reset_otp", methods=["POST"])
@limiter.limit("5 per minute")
def send_reset_otp():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip()

    if not email:
        return jsonify({"message": "Email is required", "success": False}), 400

    cur = None
    try:
        cur = mysql.connection.cursor()
        cur.execute("SELECT id FROM users WHERE email = %s", (email,))
        exists = cur.fetchone()
    finally:
        if cur:
            cur.close()

    # Always return a generic success-shaped message regardless of whether the
    # email is registered, so this endpoint can't be used to enumerate which
    # emails have accounts. We simply skip sending if it doesn't exist.
    if not exists:
        return jsonify({"message": "If that email is registered, an OTP has been sent.", "success": True})

    otp, cooldown_error = generate_and_store_otp("reset", email)
    if cooldown_error:
        return jsonify({"message": cooldown_error, "success": False}), 429

    email_content = f"""Hi,

You requested to reset your Secure Vote password.

Please enter the OTP {otp} to verify your email address.

The code is valid for 5 minutes.

If you did not request this, you can safely ignore this email — your password will not change.

Regards,
The Secure Vote Team"""

    ok, message = send_email_via_api(email, "Password Reset OTP", email_content)
    if not ok:
        _clear_otp_session("reset")
        return jsonify({"message": message, "success": False}), 502
    return jsonify({"message": "If that email is registered, an OTP has been sent.", "success": True})


@app.route("/verify_reset_otp", methods=["POST"])
@limiter.limit("10 per minute")
def verify_reset_otp():
    data = request.get_json(silent=True) or {}
    entered_otp = data.get("otp")
    email = session.get("reset_email")

    if not entered_otp:
        return jsonify({"message": "OTP is required", "success": False}), 400
    if not email:
        return jsonify({"message": "No OTP request found. Please request a new OTP.", "success": False}), 400

    valid, error = is_otp_valid("reset", email, entered_otp)
    if not valid:
        return jsonify({"message": error, "success": False}), 400

    # This is the actual authorization gate for /reset_password below — the
    # previous version let anyone who could set session["reset_email"] (i.e.
    # anyone who just called /send_reset_otp with a victim's email) reset that
    # victim's password *without ever entering the OTP*. Now reset_password
    # additionally requires this flag, set only here, on successful
    # verification, with its own short expiry.
    session["reset_verified_email"] = email
    session["reset_verified_time"] = time.time()
    _clear_otp_session("reset")
    return jsonify({"message": "OTP verified successfully!", "success": True})


@app.route("/reset_password", methods=["POST"])
@limiter.limit("5 per minute")
def reset_password():
    data = request.get_json(silent=True) or {}
    new_password = data.get("password")

    verified_email = session.get("reset_verified_email")
    verified_time = session.get("reset_verified_time")

    if not verified_email or not verified_time:
        return jsonify({"message": "Please verify the OTP before resetting your password.", "success": False}), 400
    if time.time() - verified_time > RESET_VERIFIED_TTL:
        session.pop("reset_verified_email", None)
        session.pop("reset_verified_time", None)
        return jsonify({"message": "Verification expired. Please request a new OTP.", "success": False}), 400
    if not new_password or len(new_password) < 8:
        return jsonify({"message": "Password must be at least 8 characters.", "success": False}), 400

    hashed_password = generate_password_hash(new_password)
    cur = None
    try:
        cur = mysql.connection.cursor()
        cur.execute(
            "UPDATE users SET password = %s WHERE email = %s",
            (hashed_password, verified_email)
        )
        mysql.connection.commit()

        session.pop("reset_verified_email", None)
        session.pop("reset_verified_time", None)
        return jsonify({"message": "Password reset successful!", "success": True})
    except Exception as e:
        mysql.connection.rollback()
        print("Error resetting password:", str(e))
        return jsonify({"message": "Error resetting password. Please try again.", "success": False}), 500
    finally:
        if cur:
            cur.close()


# Ensure upload directory exists
UPLOAD_FOLDER = "static/uploads/profiles"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

MAX_PROFILE_PIC_BYTES = 2 * 1024 * 1024  # 2MB
ALLOWED_IMAGE_FORMATS = {"JPEG", "PNG", "GIF", "WEBP"}


class ProfilePictureError(ValueError):
    """Raised for any invalid upload; message is safe to show the user."""


def save_profile_picture(profile_pic, user_id):
    """Validate and save a profile picture, returning its relative path.

    The previous version called profile_pic.save() directly on whatever was
    uploaded — it trusted the browser-supplied filename/content-type and
    never looked at the actual bytes. That means anyone could upload an
    arbitrary file (HTML/SVG-with-script/polyglot/oversized file) that would
    then be served back out from /uploads/profiles/... on the same origin as
    the login page. Along with a missing X-Content-Type-Options header (now
    added, see add_header()), that's a textbook way to end up flagged by
    Safe Browsing as serving "harmful content". This version:
      - caps the upload size before touching it
      - decodes it with Pillow and verifies it's really one of the allowed
        image formats (a renamed .html/.svg/.exe will fail here)
      - re-encodes it as a fresh JPEG rather than saving the uploaded bytes
        verbatim, which also strips any non-image payload smuggled inside a
        technically-valid image container (e.g. an EXIF/XMP-based polyglot)
      - always writes to the fixed, server-generated `user_<id>.jpg` path —
        no part of the filename is ever taken from user input, so path
        traversal isn't reachable here regardless.
    """
    if not profile_pic or not profile_pic.filename:
        return None

    profile_pic.seek(0, os.SEEK_END)
    size = profile_pic.tell()
    profile_pic.seek(0)
    if size > MAX_PROFILE_PIC_BYTES:
        raise ProfilePictureError("Image must be smaller than 2MB.")
    if size == 0:
        raise ProfilePictureError("Uploaded file is empty.")

    try:
        from PIL import Image
        img = Image.open(profile_pic)
        img.verify()  # cheap structural check
        profile_pic.seek(0)
        img = Image.open(profile_pic)  # verify() leaves the image unusable, reopen
        if img.format not in ALLOWED_IMAGE_FORMATS:
            raise ProfilePictureError("Unsupported image format. Use JPEG, PNG, GIF, or WEBP.")
        img = img.convert("RGB")
    except ProfilePictureError:
        raise
    except Exception:
        raise ProfilePictureError("The uploaded file is not a valid image.")

    filename = f"user_{user_id}.jpg"
    profile_pic_path = os.path.join(UPLOAD_FOLDER, filename)
    img.save(profile_pic_path, format="JPEG", quality=85)
    return f"uploads/profiles/{filename}"


@app.route("/update_profile", methods=["POST"])
@limiter.limit("10 per minute")
def update_profile():
    """Updates user profile for both admin and voter."""
    if not session.get("logged_in"):
        return jsonify({"error": "Unauthorized"}), 403

    user_id = session["user_id"]
    name = (request.form.get("name") or "").strip()
    email = (request.form.get("email") or "").strip()
    profile_pic = request.files.get("profile-pic-input")

    if not name or not email:
        return jsonify({"status": "error", "message": "Name and email are required."}), 400
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        return jsonify({"status": "error", "message": "Please enter a valid email address."}), 400

    cursor = mysql.connection.cursor()
    try:
        cursor.execute("SELECT profile_pic FROM users WHERE id = %s", (user_id,))
        current_pic = cursor.fetchone()
        current_pic = current_pic[0] if current_pic else None

        cursor.execute("SELECT id FROM users WHERE email = %s AND id != %s", (email, user_id))
        if cursor.fetchone():
            return jsonify({"status": "error", "message": "That email is already in use by another account."}), 400

        try:
            profile_pic_path = save_profile_picture(profile_pic, user_id) or current_pic
        except ProfilePictureError as e:
            return jsonify({"status": "error", "message": str(e)}), 400

        cursor.execute(
            "UPDATE users SET name = %s, email = %s, profile_pic = %s WHERE id = %s",
            (name, email, profile_pic_path, user_id)
        )
        mysql.connection.commit()

        # Update session
        session.update({
            "name": name,
            "username": email,
            "profile_pic": profile_pic_path,
            "timestamp": int(time.time())
        })

        add_notification(user_id, "Your profile has been updated successfully.")

        if profile_pic_path:
            static_relative = profile_pic_path[len("static/"):] if profile_pic_path.startswith("static/") else profile_pic_path
            profile_pic_url = url_for("static", filename=static_relative) + f"?t={session['timestamp']}"
        else:
            profile_pic_url = url_for("static", filename="uploads/profiles/PU.jpg")

        return jsonify({
            "status": "success",
            "message": "Profile updated successfully!",
            "profile_pic": profile_pic_url
        })

    except Exception as e:
        mysql.connection.rollback()
        print("Error updating profile:", str(e))
        return jsonify({"status": "error", "message": "Profile update failed!"}), 400
    finally:
        cursor.close()


@app.route("/change_password", methods=["POST"])
@limiter.limit("10 per minute")
def change_password():
    if not session.get("logged_in"):
        return redirect(url_for("login"))

    try:
        current_password = request.form.get("current-password", "")
        new_password = request.form.get("new-password", "")
        user_id = session.get("user_id")

        if not user_id:
            return jsonify({"message": "User session expired. Please log in again."}), 401
        if len(new_password) < 8:
            return jsonify({"message": "New password must be at least 8 characters."}), 400

        cursor = mysql.connection.cursor()
        cursor.execute("SELECT password FROM users WHERE id = %s", (user_id,))
        user = cursor.fetchone()
        
        if not user or not check_password_hash(user[0], current_password):
            cursor.close()
            return jsonify({"message": "Current password is incorrect!"}), 400

        hashed_password = generate_password_hash(new_password)
        cursor.execute("UPDATE users SET password = %s WHERE id = %s", (hashed_password, user_id))
        mysql.connection.commit()
        cursor.close()

        add_notification(user_id, "Your password has been changed successfully.")
        return jsonify({"message": "Password changed successfully!"})

    except Exception as e:
        print(f"Error changing password: {e}")
        return jsonify({"message": "Error changing password"}), 500
@app.route('/add_election', methods=['GET', 'POST'])
@admin_required
def add_election():
    if request.method == 'POST':
        # Retrieve form data safely
        title = request.form.get('title', "").strip()
        description = request.form.get('description', "").strip()
        status = request.form.get('status', "").strip()
        start_date = request.form.get('start_date', "").strip()
        end_date = request.form.get('end_date', "").strip()
        candidates = request.form.getlist('candidates[]')

        # ✅ Validate required fields
        if not all([title, description, status, start_date, end_date]):
            flash("All fields are required!", "add_error")
            return redirect(url_for('electionform'))

        if status not in {"upcoming", "active", "completed", "Upcoming", "Active", "Completed"}:
            flash("Invalid election status.", "add_error")
            return redirect(url_for('electionform'))
        status = status.lower()

        # Validate date format and order
        try:
            start_date_obj = datetime.strptime(start_date, "%Y-%m-%d")
            end_date_obj = datetime.strptime(end_date, "%Y-%m-%d")
            if end_date_obj <= start_date_obj:
                flash("End date must be after start date.", "add_error")
                return redirect(url_for('electionform'))
        except ValueError:
            flash("Invalid date format.", "add_error")
            return redirect(url_for('electionform'))

        cursor = None
        try:
            cursor = mysql.connection.cursor()
            valid_candidates = []

            # ✅ Validate candidates only once (strip + check DB)
            for candidate in candidates:
                if "/" not in candidate:
                    flash(f"Invalid format for candidate: {candidate}. Use Name/VoterID.", "add_error")
                    continue

                name, voterId = map(str.strip, candidate.split("/", 1))

                cursor.execute("SELECT id FROM users WHERE voterId = %s AND name = %s", (voterId, name))
                if cursor.fetchone():
                    valid_candidates.append((name, voterId))
                else:
                    flash(f"Candidate '{name}' with Voter ID '{voterId}' not registered. Skipping.", "warning")

            # ✅ Ensure at least one candidate is valid
            if not valid_candidates:
                flash("No valid candidates to add. Please try again.", "add_error")
                return redirect(url_for('electionform'))

            # ✅ Insert election
            cursor.execute(
                "INSERT INTO elections (title, description, status, start_date, end_date) VALUES (%s, %s, %s, %s, %s)",
                (title, description, status, start_date, end_date)
            )
            election_id = cursor.lastrowid

            # ✅ Insert all valid candidates in batch (faster than loop commits)
            cursor.executemany(
                "INSERT INTO candidates (election_id, voterId, name) VALUES (%s, %s, %s)",
                [(election_id, voterId, name) for name, voterId in valid_candidates]
            )

            mysql.connection.commit()
            add_notification_to_all_users(f"A new election '{title}' has been added. Check now!")
            flash("Election and candidates added successfully!", "add_success")
            return redirect(url_for('admin'))

        except Exception as e:
            mysql.connection.rollback()
            print("Error adding election:", str(e))
            flash("Something went wrong while creating the election. Please try again.", "add_error")
            return redirect(url_for('electionform'))

        finally:
            if cursor:
                cursor.close()

    # ✅ GET request → show admin form
    return render_template('admin.html')

@app.route('/voting')
@login_required
def vote():
    cursor = None
    try:
        today = datetime.today().date()
        user_role = session.get('role')
        dark_mode = session.get('dark_mode', False)

        cursor = mysql.connection.cursor()
        cursor.execute("SELECT id, title, description, start_date, end_date FROM elections")
        elections = cursor.fetchall()

        election_list = []

        for election in elections:
            # Unpack election tuple safely
            election_id, title, description, start_date, end_date = election

            # Ensure start_date and end_date are date objects
            start_date = start_date if isinstance(start_date, date) else datetime.strptime(str(start_date), "%Y-%m-%d").date()
            end_date = end_date if isinstance(end_date, date) else datetime.strptime(str(end_date), "%Y-%m-%d").date()

            # Determine status and button
            if today >= end_date:
                status, click_text, url = "Completed", "View Results", f"/results/{election_id}"

                # Notify users once when election ends (bulk insert, not a per-user loop)
                cursor.execute("SELECT EXISTS(SELECT 1 FROM notifications WHERE message = %s)", 
                               (f"The election '{title}' has ended! Check out the results now.",))
                if not cursor.fetchone()[0]:
                    add_notification_to_all_users(f"The election '{title}' has ended! Check out the results now.")

            elif today < start_date:
                status, click_text, url = "Upcoming", "Not Started", "#"

                # Notify users 2 days before election (bulk insert, not a per-user loop)
                if (start_date - today).days == 2:
                    cursor.execute("SELECT EXISTS(SELECT 1 FROM notifications WHERE message = %s)", 
                                   (f"The election '{title}' is starting in 2 days! Get ready to vote.",))
                    if not cursor.fetchone()[0]:
                        add_notification_to_all_users(f"The election '{title}' is starting in 2 days! Get ready to vote.")

            else:
                status, click_text, url = "Active", "Vote Now", f"/votes/{election_id}"

            election_list.append({
                "id": election_id,
                "title": title,
                "description": description,
                "startDate": start_date.strftime("%Y-%m-%d"),
                "endDate": end_date.strftime("%Y-%m-%d"),
                "status": status,
                "click": click_text,
                "url": url
            })

        template = 'adminvote.html' if user_role == 'admin' else 'Voting.html'
        return render_template(template, 
                               elections=election_list, 
                               current_date=today.strftime("%Y-%m-%d"),
                               dark_mode=dark_mode)

    except Exception as e:
        print("Error fetching elections:", str(e))
        flash("Couldn't load elections right now. Please try again.", "danger")
        return render_template('Voting.html', elections=[], current_date=today.strftime("%Y-%m-%d"), dark_mode=dark_mode)

    finally:
        if cursor:
            cursor.close()


@app.route('/update_election/<int:election_id>', methods=['GET', 'POST'])
@admin_required
def update_election(election_id):
    cursor = mysql.connection.cursor()

    # Fetch election
    cursor.execute("SELECT * FROM elections WHERE id = %s", (election_id,))
    election = cursor.fetchone()
    if not election:
        cursor.close()
        flash("Election not found!", "error")
        return redirect(url_for('admin'))

    election = {
        "id": election[0],
        "title": election[1],
        "description": election[2],
        "status": election[3],
        "start_date": election[4],
        "end_date": election[5]
    }

    # Fetch candidates
    cursor.execute("SELECT id, name, voterId FROM candidates WHERE election_id = %s", (election_id,))
    candidates = [{"id": cid, "name": name, "voterId": voterId} for cid, name, voterId in cursor.fetchall()]

    if request.method == 'POST':
        title = request.form.get('title', "").strip()
        description = request.form.get('description', "").strip()
        status = request.form.get('status', "").strip()
        start_date = request.form.get('start_date', "").strip()
        end_date = request.form.get('end_date', "").strip()
        new_candidates = request.form.getlist('candidates[]')
        delete_candidates = request.form.getlist('delete_candidates[]')

        try:
            start_date_obj = datetime.strptime(start_date, "%Y-%m-%d")
            end_date_obj = datetime.strptime(end_date, "%Y-%m-%d")
            if end_date_obj <= start_date_obj:
                flash("End date must be after start date.", "error")
                return redirect(url_for('update_election', election_id=election_id))
            if status not in {"upcoming", "active", "completed", "Upcoming", "Active", "Completed"}:
                flash("Invalid election status.", "error")
                return redirect(url_for('update_election', election_id=election_id))
            status = status.lower()

            # Update election
            cursor.execute("""
                UPDATE elections
                SET title=%s, description=%s, status=%s, start_date=%s, end_date=%s
                WHERE id=%s
            """, (title, description, status, start_date, end_date, election_id))

            # Delete candidates in batch
            if delete_candidates:
                cursor.executemany("DELETE FROM candidates WHERE id = %s", [(cid,) for cid in delete_candidates])

            # Add new candidates
            for candidate in new_candidates:
                if "/" not in candidate:
                    flash(f"Invalid format for candidate: {candidate}. Use Name/VoterID.", "warning")
                    continue

                name, voterId = map(str.strip, candidate.split("/", 1))
                cursor.execute("SELECT id FROM users WHERE voterId = %s AND name = %s", (voterId, name))
                if cursor.fetchone():
                    cursor.execute(
                        "INSERT INTO candidates (election_id, voterId, name) VALUES (%s, %s, %s)",
                        (election_id, voterId, name)
                    )
                else:
                    flash(f"Candidate '{name}' with Voter ID '{voterId}' not registered. Skipping.", "warning")

            mysql.connection.commit()
            flash("Election updated successfully!", "success")
            return redirect(url_for('admin'))

        except Exception as e:
            mysql.connection.rollback()
            print("Error updating election:", str(e))
            flash("Something went wrong while updating the election. Please try again.", "error")

        finally:
            cursor.close()

    return render_template('update_election.html', election=election, candidates=candidates)

@app.route('/delete_election/<int:election_id>', methods=['POST'])
@admin_required
def delete_election(election_id):
    cursor = None
    try:
        cursor = mysql.connection.cursor()
        today = datetime.today().date()

        # Fetch election details
        cursor.execute('SELECT title, end_date FROM elections WHERE id = %s', (election_id,))
        election = cursor.fetchone()

        if not election:
            flash("Election not found!", "danger")
            return redirect(url_for('admin'))

        title, end_date = election
        if isinstance(end_date, str):  # Convert string to date
            end_date = datetime.strptime(end_date, "%Y-%m-%d").date()

        if today >= end_date:
            # Delete election, candidates, and votes in one transaction
            cursor.execute('DELETE FROM votes WHERE election_id = %s', (election_id,))
            cursor.execute('DELETE FROM candidates WHERE election_id = %s', (election_id,))
            cursor.execute('DELETE FROM elections WHERE id = %s', (election_id,))

            # Notify admin
            cursor.execute("SELECT id FROM users WHERE role = 'admin' LIMIT 1")
            admin = cursor.fetchone()
            if admin:
                add_notification(admin[0], f"Election '{title}' has been deleted successfully.")

            mysql.connection.commit()
            flash("Election deleted successfully!", "success")
        else:
            flash("You can only delete elections that have ended!", "danger")

    except Exception as e:
        mysql.connection.rollback()
        print("Error deleting election:", str(e))
        flash("Something went wrong while deleting the election. Please try again.", "danger")

    finally:
        if cursor:
            cursor.close()

    return redirect(url_for('admin'))


@app.route('/votes/<int:election_id>', methods=['GET'])
def show_candidates(election_id):
    if 'user_id' not in session:
        return redirect(url_for('login', next=request.path))

    user_id = session['user_id']
    cursor = None
    try:
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

        cursor.execute(
            "SELECT id, title, start_date, end_date FROM elections WHERE id = %s",
            (election_id,)
        )
        election = cursor.fetchone()
        if not election:
            flash("Election not found.", "danger")
            return redirect(url_for('vote'))

        today = date.today()
        if today < election['start_date']:
            flash("This election has not started yet.", "warning")
            return redirect(url_for('vote'))
        if today >= election['end_date']:
            flash("This election has ended. Results are available instead.", "warning")
            return redirect(url_for('results', election_id=election_id))

        # Check if the user has already voted
        cursor.execute("SELECT 1 FROM votes WHERE user_id = %s AND election_id = %s LIMIT 1", (user_id, election_id))
        has_voted = cursor.fetchone()

        # Fetch candidates with user IDs
        cursor.execute("""
            SELECT c.id, c.name, c.voterId, u.id AS user_id
            FROM candidates c
            JOIN users u ON c.voterId = u.voterId
            WHERE c.election_id = %s
        """, (election_id,))
        candidates = cursor.fetchall()

        # Attach profile picture paths
        for candidate in candidates:
            profile_pic_path = f"uploads/profiles/user_{candidate['user_id']}.jpg"
            candidate['profile_pic'] = profile_pic_path if os.path.exists(os.path.join("static", profile_pic_path)) \
                                       else "uploads/profiles/PU.jpg"

        return render_template("vote.html", candidates=candidates, election_id=election_id, has_voted=bool(has_voted))
    except Exception as e:
        print("Error loading candidates:", str(e))
        flash("Something went wrong loading this election. Please try again.", "danger")
        return redirect(url_for('vote'))
    finally:
        if cursor:
            cursor.close()


@app.route('/submit_vote/<int:election_id>', methods=['POST'])
@login_required
def submit_vote(election_id):
    user_id = session['user_id']
    candidate_id = request.form.get('candidate_id')

    if not candidate_id or not str(candidate_id).isdigit():
        flash("Please select a candidate.", "danger")
        return redirect(url_for('show_candidates', election_id=election_id))

    cursor = None
    try:
        cursor = mysql.connection.cursor()
        cursor.execute(
            'SELECT title, start_date, end_date FROM elections WHERE id = %s',
            (election_id,)
        )
        election = cursor.fetchone()

        if not election:
            flash("Election not found.", "danger")
            return redirect(url_for('vote'))

        title, start_date, end_date = election
        today = date.today()
        if today < start_date:
            flash("This election has not started yet.", "danger")
            return redirect(url_for('vote'))
        if today >= end_date:
            flash("This election has ended. You can no longer vote.", "danger")
            return redirect(url_for('vote'))

        # Verify the candidate belongs to this election. to
        # this election — only the DB's foreign key (candidate_id exists
        # *somewhere*) was enforced. A crafted request could submit a
        # candidate_id from a *different* election and have it recorded as a
        # vote here, corrupting that other election's results.
        cursor.execute(
            'SELECT id FROM candidates WHERE id = %s AND election_id = %s',
            (candidate_id, election_id)
        )
        if not cursor.fetchone():
            flash("Invalid candidate for this election.", "danger")
            return redirect(url_for('show_candidates', election_id=election_id))

        # Explicit check first (fast path, friendly message for the common case).
        # The UNIQUE (user_id, election_id) constraint on the votes table is what
        # actually prevents a double vote if two submissions race each other —
        # this check alone isn't enough under concurrent requests, hence the
        # IntegrityError handling below as the real safety net.
        cursor.execute(
            'SELECT id FROM votes WHERE user_id = %s AND election_id = %s',
            (user_id, election_id)
        )
        if cursor.fetchone():
            flash("You have already voted in this election.", "danger")
            return redirect(url_for('vote'))

        # Insert vote
        cursor.execute('''
            INSERT INTO votes (user_id, candidate_id, election_id)
            VALUES (%s, %s, %s)
        ''', (user_id, candidate_id, election_id))

        add_notification(user_id, f"You have successfully voted in {title} election. Results will be declared on {end_date}.")

        mysql.connection.commit()
        flash("Your vote has been successfully submitted!", "success")
        return redirect(url_for('vote'))

    except MySQLdb.IntegrityError:
        # Caught by the UNIQUE (user_id, election_id) constraint — the case where
        # two submissions from the same user raced past the check above.
        mysql.connection.rollback()
        flash("You have already voted in this election.", "danger")
        return redirect(url_for('vote'))

    except Exception as e:
        mysql.connection.rollback()
        print("Error submitting vote:", str(e))  # Log detail server-side only
        flash("Something went wrong while submitting your vote. Please try again.", "danger")
        return redirect(url_for('vote'))

    finally:
        if cursor:
            cursor.close()

@app.route('/results/<int:election_id>')
@login_required
def results(election_id):
    try:
        user_role = session.get('role')

        with mysql.connection.cursor(MySQLdb.cursors.DictCursor) as cur:
            cur.execute(
                "SELECT title, status, start_date, end_date FROM elections WHERE id = %s",
                (election_id,)
            )
            election = cur.fetchone()

            if not election:
                flash("Election not found.", "danger")
                return redirect(url_for('vote'))

            election_title = election['title']
            if user_role != 'admin' and date.today() < election['end_date']:
                flash("Results will be available after the election ends.", "warning")
                return redirect(url_for('vote'))

            # Fetch candidates with aggregated vote count and user_id directly
            cur.execute("""
                SELECT c.id, c.name, c.voterId, 
                       COUNT(v.id) AS vote_count, 
                       u.id AS user_id
                FROM candidates c
                LEFT JOIN votes v ON c.id = v.candidate_id
                INNER JOIN users u ON c.voterId = u.voterId
                WHERE c.election_id = %s
                GROUP BY c.id, c.name, c.voterId, u.id
                ORDER BY vote_count DESC
            """, (election_id,))
            candidates = cur.fetchall()

        # Cache os.path.exists checks to reduce disk calls
        default_pic = "uploads/profiles/PU.jpg"
        for candidate in candidates:
            profile_pic_path = f"uploads/profiles/user_{candidate['user_id']}.jpg"
            full_path = os.path.join("static", profile_pic_path)
            candidate['profile_pic'] = profile_pic_path if os.path.exists(full_path) else default_pic

        results_data = [
            {
                "name": c['name'],
                "profile_pic": c['profile_pic'],
                "voter_id": c['voterId'],
                "vote_count": c['vote_count']
            }
            for c in candidates
        ]

        # Role-based results view
        if user_role == 'admin':
            return render_template("adminresults.html", election_title=election_title, results=results_data)
        elif user_role == 'voter':
            return render_template("results.html", election_title=election_title, results=results_data)

        flash("Results will be available after the election ends.", "warning")
        return redirect(url_for('home'))

    except Exception as e:
        print("Error loading results:", str(e))
        flash("Couldn't load results right now. Please try again.", "danger")
        return redirect(url_for('home'))


@app.route('/my_votes')
def my_votes():
    if 'user_id' not in session:
        flash("You must be logged in to view your votes.", "danger")
        return redirect(url_for('login'))

    user_id = session['user_id']

    with mysql.connection.cursor(MySQLdb.cursors.DictCursor) as cursor:
        cursor.execute("""
            SELECT e.title AS election_title, 
                   c.name AS candidate_name, 
                   c.voterId AS voter_id, 
                   u.id AS user_id
            FROM votes v
            JOIN candidates c ON v.candidate_id = c.id
            JOIN users u ON c.voterId = u.voterId
            JOIN elections e ON v.election_id = e.id
            WHERE v.user_id = %s
            ORDER BY e.start_date DESC
        """, (user_id,))
        my_votes = cursor.fetchall()

    default_pic = "uploads/profiles/PU.jpg"
    for vote in my_votes:
        profile_pic_path = f"uploads/profiles/user_{vote['user_id']}.jpg"
        full_path = os.path.join("static", profile_pic_path)
        vote['profile_pic'] = profile_pic_path if os.path.exists(full_path) else default_pic

    return render_template("my_votes.html", my_votes=my_votes)


@app.route('/admin/voter_records')
@admin_required
def admin_voter_records():
    records = []
    default_pic = "uploads/profiles/PU.jpg"

    with mysql.connection.cursor(MySQLdb.cursors.DictCursor) as cursor:
        cursor.execute("SELECT id, title FROM elections")
        elections = cursor.fetchall()

        for election in elections:
            cursor.execute("""
                SELECT u.name AS voter_name, u.voterId AS voter_id,
                       c.name AS candidate_name, c.voterId AS candidate_voter_id,
                       v.voted_at, u.id AS user_id
                FROM votes v
                JOIN users u ON v.user_id = u.id
                JOIN candidates c ON v.candidate_id = c.id
                WHERE v.election_id = %s
            """, (election['id'],))
            votes = cursor.fetchall()

            for vote in votes:
                profile_pic_path = f"uploads/profiles/user_{vote['user_id']}.jpg"
                if not os.path.exists(os.path.join("static", profile_pic_path)):
                    profile_pic_path = default_pic
                vote['candidate_pic'] = profile_pic_path

            records.append({'title': election['title'], 'votes': votes})

    return render_template("admin_voter_records.html", elections=records)


@app.route('/get-flash-messages')
def get_flash_messages():
    return jsonify(get_flashed_messages(with_categories=True))


@app.route('/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({"status": "success"})


@app.errorhandler(413)
def request_entity_too_large(_error):
    return jsonify({"message": "Uploaded data is too large.", "success": False}), 413


@app.errorhandler(429)
def rate_limit_exceeded(_error):
    return jsonify({"message": "Too many requests. Please try again later.", "success": False}), 429


if __name__ == "__main__":
    # Debug mode (the Werkzeug reloader + verbose error pages) adds real overhead
    # and was hardcoded on. Default to off; set FLASK_DEBUG=true in otp.env while developing.
    debug_mode = os.getenv("FLASK_DEBUG", "false").lower() == "true"
    # Railway/Render assign the port dynamically via $PORT — 5500 is only the local fallback.
    port = int(os.getenv("PORT", 5500))
    socketio.run(app, host="0.0.0.0", port=port, debug=debug_mode)