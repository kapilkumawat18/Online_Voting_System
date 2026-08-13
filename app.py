import eventlet
import eventlet.wsgi
from flask import Flask, render_template, request, redirect, jsonify, url_for, session , flash , send_from_directory,get_flashed_messages
from flask_mysqldb import MySQL
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime , date
from flask_mail import Mail, Message
import random
import MySQLdb.cursors
from flask_caching import Cache
import os , time
from dotenv import load_dotenv
from flask_socketio import SocketIO
from functools import wraps

load_dotenv("otp.env")

# Initialize the Flask application
app = Flask(__name__)
socketio = SocketIO(app)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'Online_Voting_System')

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
@app.after_request
def add_header(response):
    if request.path.startswith('/static/') or request.path.startswith('/uploads/'):
        response.headers["Cache-Control"] = "public, max-age=3600"
    else:
        response.headers["Cache-Control"] = "no-store"
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
def uploaded_file(filename):
    # send_from_directory already safe from path traversal
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
    user_id = request.args.get('user_id')
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
    cur = None
    try:
        cur = mysql.connection.cursor()
        cur.execute("DELETE FROM notifications WHERE id = %s", (notif_id,))
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
def login():
    # GET → show the login/register page. This is the page "necessary buttons"
    # (Vote, Home dashboard, Records, etc.) redirect to when a visitor isn't logged in.
    if request.method == 'GET':
        if session.get('logged_in'):
            return redirect(url_for('admin' if session.get('role') == 'admin' else 'home'))
        return render_template('login.html', next=request.args.get('next', ''))

    role = request.form.get('role')
    name = request.form.get('name')
    username = request.form.get('username')
    password = request.form.get('password')

    if not role or not name or not username or not password:
        flash("Please fill all fields.", "login_error")
        return redirect(url_for('login'))

    cur = None
    try:
        cur = mysql.connection.cursor()
        query = "SELECT id, password, dark_mode FROM users WHERE name=%s AND email=%s AND role=%s"
        cur.execute(query, (name, username, role))
        user = cur.fetchone()

        if not user:
            flash("Invalid login credentials, please try again.", "login_error")
            return redirect(url_for('login'))

        user_id, hashed_password, dark_mode = user

        if check_password_hash(hashed_password, password):
            # Store session data
            session.update({
                'logged_in': True,
                'user_id': user_id,
                'name': name,
                'username': username,
                'role': role,
                'dark_mode': dark_mode,
            })

            flash("Login successful!", "login_success")
            add_notification(user_id, "You have successfully logged in.")

            next_url = request.form.get('next') or request.args.get('next')
            if next_url and next_url.startswith('/'):
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
def register():
    role = request.form.get('role')
    name = request.form.get('name')
    email = request.form.get('email')
    voterId = request.form.get('voterId')
    password = request.form.get('password')

    if not all([role, name, email, voterId, password]):
        flash("All fields are required.", "login_error")
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


# Flask-Mail configuration (Gmail SMTP)
app.config.update(
    MAIL_SERVER="smtp.gmail.com",
    MAIL_PORT=587,
    MAIL_USE_TLS=True,
    MAIL_USE_SSL=False,
    MAIL_USERNAME=os.getenv("GMAIL_USER"),
    MAIL_PASSWORD=os.getenv("GMAIL_PASS"),
    MAIL_DEFAULT_SENDER=("Secure Vote", os.getenv("GMAIL_USER"))
)

mail = Mail(app)


# ----------------- OTP Helpers -----------------
def generate_and_store_otp(session_key_prefix, email):
    otp = random.randint(100000, 999999)
    session[f"{session_key_prefix}_otp"] = otp
    session[f"{session_key_prefix}_email"] = email
    session[f"{session_key_prefix}_time"] = time.time()
    return otp

def is_otp_valid(session_key_prefix, entered_otp):
    otp = session.get(f"{session_key_prefix}_otp")
    otp_time = session.get(f"{session_key_prefix}_time")

    if not otp or not otp_time:
        return False, "No OTP found or already used."

    if time.time() - otp_time > 300:  # 5 min expiry
        return False, "OTP expired. Request a new one."

    return (int(entered_otp) == otp), ("Invalid OTP." if int(entered_otp) != otp else "")


# ----------------- OTP Routes -----------------
@app.route("/send_otp", methods=["POST"])
def send_otp():
    data = request.get_json()
    email = data.get("email")

    if not email:
        return jsonify({"message": "Email is required", "success": False}), 400

    otp = generate_and_store_otp("register", email)

    email_content = f"""Hi,
Welcome to Secure Vote! You are trying to register for Secure Vote with this email address.

Please enter the OTP {otp} to verify your email address.

The code is valid for 5 minutes.

You can ignore this email if you have not made this request.

Regards,
The Secure Vote Team"""

    try:
        msg = Message("Email Verification OTP", recipients=[email], body=email_content)
        mail.send(msg)
        return jsonify({"message": "OTP sent successfully!", "success": True})
    except Exception as e:
        print(f"Error sending email: {str(e)}")
        return jsonify({"message": "OTP failed to send", "success": False}), 500


@app.route("/verify_otp", methods=["POST"])
def verify_otp():
    data = request.get_json()
    entered_otp = data.get("otp")

    if not entered_otp:
        return jsonify({"message": "OTP is required", "success": False}), 400

    valid, error = is_otp_valid("register", entered_otp)
    if not valid:
        return jsonify({"message": error, "success": False}), 400

    # Clear OTP after success
    session.pop("register_otp", None)
    return jsonify({"message": "OTP verified successfully!", "success": True})


@app.route("/send_reset_otp", methods=["POST"])
def send_reset_otp():
    data = request.get_json()
    email = data.get("email")

    if not email:
        return jsonify({"message": "Email is required", "success": False}), 400

    cur = None
    try:
        cur = mysql.connection.cursor()
        cur.execute("SELECT id FROM users WHERE email = %s", (email,))
        if not cur.fetchone():
            return jsonify({"message": "Email not registered!", "success": False}), 400
    finally:
        if cur:
            cur.close()

    otp = generate_and_store_otp("reset", email)

    email_content = f"""Hi,
Welcome to Secure Vote! You are trying to reset your password for Secure Vote with this email address.

Please enter the OTP {otp} to verify your email address.

The code is valid for 5 minutes.

You can ignore this email if you have not made this request.

Regards,
The Secure Vote Team"""

    try:
        msg = Message("Password Reset OTP", recipients=[email], body=email_content)
        mail.send(msg)
        return jsonify({"message": "OTP sent successfully!", "success": True})
    except Exception as e:
        print("Error sending reset OTP:", str(e))
        return jsonify({"message": "Failed to send OTP", "success": False}), 500


@app.route("/verify_reset_otp", methods=["POST"])
def verify_reset_otp():
    data = request.get_json()
    entered_otp = data.get("otp")

    if not entered_otp:
        return jsonify({"message": "OTP is required", "success": False}), 400

    valid, error = is_otp_valid("reset", entered_otp)
    if not valid:
        return jsonify({"message": error, "success": False}), 400

    session.pop("reset_otp", None)
    return jsonify({"message": "OTP verified successfully!", "success": True})
@app.route("/reset_password", methods=["POST"])
def reset_password():
    data = request.get_json()
    new_password = data.get("password")

    if not session.get("reset_email"):
        return jsonify({"message": "Unauthorized action!", "success": False}), 400

    hashed_password = generate_password_hash(new_password)

    try:
        cur = mysql.connection.cursor()
        cur.execute(
            "UPDATE users SET password = %s WHERE email = %s",
            (hashed_password, session["reset_email"])
        )
        mysql.connection.commit()
        cur.close()

        session.pop("reset_email", None)
        return jsonify({"message": "Password reset successful!", "success": True})
    except Exception as e:
        return jsonify({"message": "Error resetting password!", "success": False}), 500


# Ensure upload directory exists
UPLOAD_FOLDER = "static/uploads/profiles"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def save_profile_picture(profile_pic, user_id):
    """Saves profile picture and returns relative file path."""
    if not profile_pic:
        return None
    filename = f"user_{user_id}.jpg"
    profile_pic_path = os.path.join(UPLOAD_FOLDER, filename)
    profile_pic.save(profile_pic_path)
    return f"uploads/profiles/{filename}"


@app.route("/update_profile", methods=["POST"])
def update_profile():
    """Updates user profile for both admin and voter."""
    if not session.get("logged_in"):
        return jsonify({"error": "Unauthorized"}), 403

    user_id = session["user_id"]
    name = request.form["name"]
    email = request.form["email"]
    profile_pic = request.files.get("profile-pic-input")

    cursor = mysql.connection.cursor()
    cursor.execute("SELECT profile_pic FROM users WHERE id = %s", (user_id,))
    current_pic = cursor.fetchone()
    current_pic = current_pic[0] if current_pic else None

    # Save new picture only if uploaded
    profile_pic_path = save_profile_picture(profile_pic, user_id) or current_pic

    try:
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

        profile_pic_url = (
            url_for("static", filename=profile_pic_path.lstrip("static/")) + f"?t={session['timestamp']}"
            if profile_pic_path else url_for("static", filename="uploads/profiles/PU.jpg")
        )

        return jsonify({
            "status": "success",
            "message": "Profile updated successfully!",
            "profile_pic": profile_pic_url
        })

    except Exception:
        mysql.connection.rollback()
        return jsonify({"status": "error", "message": "Profile update failed!"}), 400
    finally:
        cursor.close()


@app.route("/change_password", methods=["POST"])
def change_password():
    if not session.get("logged_in"):
        return redirect(url_for("login"))

    try:
        current_password = request.form["current-password"]
        new_password = request.form["new-password"]
        user_id = session.get("user_id")

        if not user_id:
            return jsonify({"message": "User session expired. Please log in again."}), 401

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

        # ✅ Validate date format and order
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
            flash(f"An error occurred: {str(e)}", "add_error")
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
        flash(f"Error fetching elections: {str(e)}", "danger")
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
            flash(f"Error updating election: {str(e)}", "error")

        finally:
            cursor.close()

    return render_template('update_election.html', election=election, candidates=candidates)

@app.route('/delete_election/<int:election_id>', methods=['POST'])
@admin_required
def delete_election(election_id):
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
        flash(f"Error deleting election: {str(e)}", "danger")

    finally:
        cursor.close()

    return redirect(url_for('admin'))


@app.route('/votes/<int:election_id>', methods=['GET'])
def show_candidates(election_id):
    if 'user_id' not in session:
        return redirect(url_for('login', next=request.url))

    user_id = session['user_id']
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

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

    cursor.close()
    return render_template("vote.html", candidates=candidates, election_id=election_id, has_voted=bool(has_voted))


@app.route('/submit_vote/<int:election_id>', methods=['POST'])
@login_required
def submit_vote(election_id):
    user_id = session['user_id']
    candidate_id = request.form['candidate_id']

    cursor = None
    try:
        cursor = mysql.connection.cursor()
        cursor.execute('SELECT title, end_date FROM elections WHERE id = %s', (election_id,))
        election = cursor.fetchone()

        if not election:
            flash("Election not found.", "danger")
            return redirect(url_for('vote'))

        title, end_date = election

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
def results(election_id):
    try:
        user_role = session.get('role')

        # Use a single cursor with context manager
        with mysql.connection.cursor(MySQLdb.cursors.DictCursor) as cur:
            # Fetch election details
            cur.execute("SELECT title, status FROM elections WHERE id = %s", (election_id,))
            election = cur.fetchone()

            if not election:
                flash("Election not found.", "danger")
                return redirect(url_for('home'))

            election_title = election['title']

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
        flash(f"Error loading results: {str(e)}", "danger")
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


if __name__ == "__main__":
    # Debug mode (the Werkzeug reloader + verbose error pages) adds real overhead
    # and was hardcoded on. Default to off; set FLASK_DEBUG=true in otp.env while developing.
    debug_mode = os.getenv("FLASK_DEBUG", "false").lower() == "true"
    # Railway/Render assign the port dynamically via $PORT — 5500 is only the local fallback.
    port = int(os.getenv("PORT", 5500))
    socketio.run(app, host="0.0.0.0", port=port, debug=debug_mode)
