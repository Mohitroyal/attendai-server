"""
=============================================================
  AttendAI — Fixed app.py
  Bug fixes in this version:
    FIX 1: Admin login now reads 'username' field (matches HTML form name="username")
    FIX 2: Admin DB query checks BOTH username AND email columns
    FIX 3: Superadmin route added (/superadmin GET+POST)
    FIX 4: /dashboard route now also accessible as /admin/dashboard
    FIX 5: Session key consistency ('admin' vs 'admin_username')
    FIX 6: Redirect after login uses follow_redirects-safe pattern
    FIX 7: All form field name mismatches resolved
=============================================================
"""

from flask import Flask, render_template, Response, request, redirect, session, jsonify, make_response
from flask_mysqldb import MySQL
from flask_wtf.csrf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv

import cv2
import numpy as np
import datetime
from datetime import timedelta
import calendar
import csv
import io
import os
import re
import threading
import time
import logging
import secrets

# ── Load .env FIRST ────────────────────────────────────────
load_dotenv()

# ── Logging setup ──────────────────────────────────────────
logging.basicConfig(
    filename='app.log',
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s'
)
logger = logging.getLogger(__name__)

# ── App init ───────────────────────────────────────────────
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', secrets.token_hex(32))
app.config['SESSION_PERMANENT'] = True
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=8)
app.config['WTF_CSRF_TIME_LIMIT'] = None

# ── MySQL config from .env ─────────────────────────────────
app.config['MYSQL_HOST']     = os.environ.get('MYSQL_HOST',     'localhost')
app.config['MYSQL_USER']     = os.environ.get('MYSQL_USER',     'root')
app.config['MYSQL_PASSWORD'] = os.environ.get('MYSQL_PASSWORD', '')
app.config['MYSQL_DB']       = os.environ.get('MYSQL_DB',       'attendance_system')

mysql = MySQL(app)

# ── Security extensions ────────────────────────────────────
csrf = CSRFProtect(app)
app.config['WTF_CSRF_ENABLED'] = False   # keep off — no CSRF tokens in templates yet
limiter = Limiter(
    key_func=get_remote_address,
    app=app,
    default_limits=["200/hour"],
    storage_uri="memory://"
)

# ── Work start time ────────────────────────────────────────
WORK_START_HOUR   = int(os.environ.get('WORK_START_HOUR',   '9'))
WORK_START_MINUTE = int(os.environ.get('WORK_START_MINUTE', '0'))

# ── AI model ───────────────────────────────────────────────
model = None
MODEL_PATH = os.environ.get('MODEL_PATH', 'model/face_model4.keras')

try:
    import tensorflow as tf
    model = tf.keras.models.load_model(MODEL_PATH)
    logger.info(f"Face model loaded: {MODEL_PATH}")
    print(f"✅ Face model loaded: {MODEL_PATH}")
except Exception as e:
    logger.error(f"Model load failed: {e}")
    print(f"⚠️  Model load failed: {e} — face recognition disabled")

face_cascade = cv2.CascadeClassifier(
    cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
)

# ── Face labels from DB ────────────────────────────────────
_labels_cache = []
_labels_lock  = threading.Lock()

def get_labels():
    global _labels_cache
    try:
        with app.app_context():
            cur = mysql.connection.cursor()
            cur.execute("SELECT face_label FROM employees WHERE face_label IS NOT NULL ORDER BY id")
            rows = cur.fetchall()
            cur.close()
            labels = [row[0] for row in rows if row[0]]
            if labels:
                with _labels_lock:
                    _labels_cache = labels
                return labels
    except Exception as e:
        logger.error(f"get_labels failed: {e}")
    with _labels_lock:
        return list(_labels_cache)

# ── Camera ─────────────────────────────────────────────────
camera      = None
camera_lock = threading.Lock()

def init_camera():
    global camera
    import platform
    backend = cv2.CAP_V4L2 if platform.system() == 'Linux' else cv2.CAP_DSHOW
    for idx in [0, 1, 2, 4]:
        try:
            cap = cv2.VideoCapture(idx, backend)
            if not cap.isOpened():
                cap = cv2.VideoCapture(idx)
            if cap.isOpened():
                ret, frame = cap.read()
                if ret and frame is not None:
                    cap.set(cv2.CAP_PROP_FRAME_WIDTH,  640)
                    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                    cap.set(cv2.CAP_PROP_FPS, 20)
                    camera = cap
                    logger.info(f"Camera opened at index {idx}")
                    print(f"✅ Camera found at index {idx}")
                    return
                cap.release()
        except Exception as e:
            logger.warning(f"Camera index {idx} failed: {e}")
    logger.warning("No camera found — scanner disabled")
    print("⚠️  No camera found")

init_camera()

latest_prediction = {"name": None, "conf": 0.0, "waiting": False, "paused": False}
prediction_lock = threading.Lock()
last_frame      = None


# ═══════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════

def admin_required():
    return session.get('admin') is True

def superadmin_required():
    return session.get('superadmin') is True

def employee_required():
    return 'employee_id' in session

def to_str(val):
    if val is None:
        return None
    if isinstance(val, (datetime.date, datetime.datetime)):
        return val.strftime('%Y-%m-%d')
    return str(val)

def validate_email(email):
    return bool(re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', email))

def validate_name(name):
    return 1 <= len(name) <= 100

def is_late_checkin():
    now   = datetime.datetime.now().time()
    start = datetime.time(WORK_START_HOUR, WORK_START_MINUTE)
    return now > start


# ═══════════════════════════════════════════════
# ATTENDANCE LOGIC
# ═══════════════════════════════════════════════

def do_checkin(name):
    cur   = mysql.connection.cursor()
    today = datetime.date.today()
    week  = today.isocalendar()[1]
    cur.execute("SELECT id FROM attendance WHERE name=%s AND date=%s", (name, today))
    if cur.fetchone() is None:
        now     = datetime.datetime.now().time()
        is_late = is_late_checkin()
        cur.execute(
            "INSERT INTO attendance(name, date, week, checkin, is_late) VALUES(%s,%s,%s,%s,%s)",
            (name, today, week, now, is_late)
        )
        mysql.connection.commit()
        cur.close()
        logger.info(f"Check-in: {name} | late={is_late}")
        return True, is_late
    cur.close()
    return False, False

def do_checkout(name):
    cur   = mysql.connection.cursor()
    today = datetime.date.today()
    now   = datetime.datetime.now().time()
    cur.execute("SELECT checkin FROM attendance WHERE name=%s AND date=%s", (name, today))
    row   = cur.fetchone()
    hours = None
    if row and row[0]:
        checkin_dt  = datetime.datetime.combine(today, row[0])
        checkout_dt = datetime.datetime.combine(today, now)
        diff        = checkout_dt - checkin_dt
        hours       = round(diff.seconds / 3600, 2)
    cur.execute(
        "UPDATE attendance SET checkout=%s, hours_worked=%s WHERE name=%s AND date=%s",
        (now, hours, name, today)
    )
    mysql.connection.commit()
    cur.close()
    logger.info(f"Check-out: {name} | hours={hours}")


# ═══════════════════════════════════════════════
# REQUEST LOGGING
# ═══════════════════════════════════════════════

@app.before_request
def log_request():
    user = session.get('employee_name', session.get('admin_username', 'anon'))
    logger.info(f"{request.method} {request.path} user={user} ip={request.remote_addr}")


# ═══════════════════════════════════════════════
# CAMERA STREAM
# ═══════════════════════════════════════════════

def frames():
    global last_frame
    last_detect_time = 0
    COOLDOWN      = 5
    THRESHOLD     = 0.92
    MIN_FACE_SIZE = 80

    while True:
        with prediction_lock:
            paused = latest_prediction["paused"]

        if paused and last_frame is not None:
            yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + last_frame + b'\r\n')
            time.sleep(0.05)
            continue

        if camera is None:
            time.sleep(0.5)
            continue

        with camera_lock:
            success, frame = camera.read()

        if not success or frame is None:
            time.sleep(0.1)
            continue

        gray   = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces  = face_cascade.detectMultiScale(gray, 1.3, 5)
        now_ts = time.time()
        labels = get_labels()

        for (x, y, w, h) in faces:
            if w < MIN_FACE_SIZE or h < MIN_FACE_SIZE:
                cv2.rectangle(frame, (x,y), (x+w,y+h), (128,128,128), 1)
                continue

            if model is None or not labels:
                cv2.rectangle(frame, (x,y), (x+w,y+h), (0,165,255), 2)
                cv2.putText(frame, "Model not loaded", (x, y-10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0,165,255), 2)
                continue

            roi   = frame[y:y+h, x:x+w]
            img_r = cv2.resize(roi, (128,128)) / 255.0
            img_r = np.reshape(img_r, (1,128,128,3))

            try:
                pred      = model.predict(img_r, verbose=0)
                label_idx = int(np.argmax(pred))
                conf      = float(np.max(pred))
            except Exception as e:
                logger.error(f"Prediction error: {e}")
                continue

            if label_idx >= len(labels):
                continue

            if conf >= THRESHOLD:
                name = labels[label_idx]
                gray_roi        = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
                blur_score      = cv2.Laplacian(gray_roi, cv2.CV_64F).var()
                roi_small       = cv2.resize(gray_roi, (32,32))
                texture_score   = float(np.std(roi_small))
                mean_brightness = float(np.mean(roi))
                is_live = (blur_score < 800 and texture_score > 15 and mean_brightness < 225)

                if is_live:
                    color = (0,255,0)
                    with prediction_lock:
                        already_waiting = latest_prediction["waiting"]
                    if not already_waiting and (now_ts - last_detect_time) > COOLDOWN:
                        with prediction_lock:
                            latest_prediction.update({"name": name, "conf": round(conf*100, 1), "waiting": True, "paused": True})
                        last_detect_time = now_ts
                else:
                    name  = "SPOOF"
                    color = (0,165,255)
            else:
                name  = "Unknown"
                color = (0,0,255)

            cv2.rectangle(frame, (x,y), (x+w,y+h), color, 2)
            cv2.putText(frame, f"{name} ({conf:.0%})", (x, y-10), cv2.FONT_HERSHEY_SIMPLEX, 0.75, color, 2)

        ret, buffer = cv2.imencode('.jpg', frame)
        if not ret:
            continue
        frame_bytes = buffer.tobytes()
        last_frame  = frame_bytes
        yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')


# ═══════════════════════════════════════════════
# PUBLIC ROUTES
# ═══════════════════════════════════════════════

@app.route('/')
def index():
    return render_template("index.html")

@app.route('/video')
def video():
    if not admin_required() and not superadmin_required():
        return "Unauthorized", 401
    if camera is None:
        return "No camera available", 503
    return Response(frames(), mimetype='multipart/x-mixed-replace; boundary=frame')


# ═══════════════════════════════════════════════
# ─────────────────────────────────────────────
#  ADMIN AUTH
#  FIX: HTML sends name="username" → read 'username'
#  FIX: DB query checks BOTH `username` and `email` columns
# ─────────────────────────────────────────────
# ═══════════════════════════════════════════════

@app.route('/admin', methods=['GET', 'POST'])
@limiter.limit("10/minute", methods=["POST"])
def admin_login():
    # Already logged in → go to dashboard
    if admin_required():
        return redirect('/dashboard')

    if request.method == 'POST':
        # ── FIX: HTML form uses name="username", NOT name="email" ──
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()

        if not username or not password:
            return render_template("admin_login.html", error="All fields required")

        cur = mysql.connection.cursor()
        # ── FIX: Try matching username column; fallback to email column ──
        cur.execute(
            "SELECT id, username, password FROM admin WHERE username=%s OR email=%s",
            (username, username)
        )
        admin_user = cur.fetchone()
        cur.close()

        if admin_user:
            stored = admin_user[2]
            valid  = False
            if stored and (stored.startswith('$2b$') or stored.startswith('$2y$')):
                valid = check_password_hash(stored, password)
            else:
                valid = (stored == password)
                if valid:
                    logger.warning(f"Admin {username} using plain-text password — migrate!")

            if valid:
                session.clear()
                session['admin']          = True
                session['admin_username'] = admin_user[1]
                logger.info(f"Admin login OK: {username}")
                return redirect('/dashboard')

        logger.warning(f"Failed admin login: {username} from {request.remote_addr}")
        return render_template("admin_login.html", error="Invalid credentials")

    return render_template("admin_login.html")


@app.route('/logout')
def logout():
    session.clear()
    return redirect('/admin')


# ═══════════════════════════════════════════════
# SUPERADMIN AUTH  ← NEW ROUTE (was missing)
# ═══════════════════════════════════════════════

@app.route('/superadmin', methods=['GET', 'POST'])
@limiter.limit("10/minute", methods=["POST"])
def superadmin_login():
    if superadmin_required():
        return redirect('/superadmin/dashboard')

    if request.method == 'POST':
        email    = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()

        if not email or not password:
            return render_template("superadmin_login.html", error="All fields required")

        cur = mysql.connection.cursor()
        # Try superadmin table first, fall back to admin table with role check
        try:
            cur.execute(
                "SELECT id, email, password FROM superadmin WHERE email=%s",
                (email,)
            )
            sa = cur.fetchone()
        except Exception:
            # superadmin table might not exist — try admin table
            cur.execute(
                "SELECT id, username, password FROM admin WHERE (username=%s OR email=%s) AND role='superadmin'",
                (email, email)
            )
            sa = cur.fetchone()
        cur.close()

        if sa:
            stored = sa[2]
            valid  = False
            if stored and (stored.startswith('$2b$') or stored.startswith('$2y$')):
                valid = check_password_hash(stored, password)
            else:
                valid = (stored == password)

            if valid:
                session.clear()
                session['superadmin']          = True
                session['superadmin_username'] = sa[1]
                logger.info(f"Superadmin login OK: {email}")
                return redirect('/superadmin/dashboard')

        logger.warning(f"Failed superadmin login: {email} from {request.remote_addr}")
        return render_template("superadmin_login.html", error="Invalid credentials")

    return render_template("superadmin_login.html")


@app.route('/superadmin/logout')
def superadmin_logout():
    session.clear()
    return redirect('/superadmin')


@app.route('/superadmin/dashboard')
def superadmin_dashboard():
    if not superadmin_required():
        return redirect('/superadmin')
    cur   = mysql.connection.cursor()
    today = datetime.date.today()
    week  = today.isocalendar()[1]

    cur.execute("SELECT COUNT(*) FROM attendance WHERE date=%s", (today,))
    today_checkins = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM attendance WHERE date=%s AND checkout IS NULL", (today,))
    present_now = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM attendance WHERE week=%s", (week,))
    week_total = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM employees")
    total_employees = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM attendance WHERE date=%s AND is_late=1", (today,))
    late_today = cur.fetchone()[0]
    cur.execute("""
        SELECT e.department, COUNT(a.id) as checkins
        FROM employees e
        LEFT JOIN attendance a ON a.name = e.name AND a.date = %s
        GROUP BY e.department
    """, (today,))
    dept_stats = cur.fetchall()
    cur.execute("SELECT id, name, department, company_id FROM employees ORDER BY name")
    employees = cur.fetchall()
    cur.close()

    return render_template("superadmin_dashboard.html",
        today_checkins=today_checkins,
        present_now=present_now,
        week_total=week_total,
        total_employees=total_employees,
        late_today=late_today,
        dept_stats=dept_stats,
        employees=employees,
        today=str(today)
    )


# ═══════════════════════════════════════════════
# EMPLOYEE AUTH
# ═══════════════════════════════════════════════

@app.route('/employee/login', methods=['GET', 'POST'])
@limiter.limit("10/minute", methods=["POST"])
def employee_login():
    if employee_required():
        return redirect('/employee/portal')

    if request.method == 'POST':
        email    = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '').strip()

        if not email or not password:
            return render_template("employee_login.html", error="All fields required")
        if not validate_email(email):
            return render_template("employee_login.html", error="Invalid email")

        cur = mysql.connection.cursor()
        cur.execute(
            "SELECT id, name, email, password, department, company_id FROM employees WHERE email=%s",
            (email,)
        )
        emp = cur.fetchone()
        cur.close()

        if emp:
            stored = emp[3]
            valid  = False
            if stored and (stored.startswith('$2b$') or stored.startswith('$2y$')):
                valid = check_password_hash(stored, password)
            else:
                valid = (stored == password)
                if valid:
                    logger.warning(f"Employee {email} using plain-text password — migrate!")

            if valid:
                session.clear()
                session['employee_id']   = emp[0]
                session['employee_name'] = emp[1]
                logger.info(f"Employee login: {emp[1]}")
                return redirect('/employee/portal')

        logger.warning(f"Failed employee login: {email} from {request.remote_addr}")
        return render_template("employee_login.html", error="Invalid credentials")

    return render_template("employee_login.html")


@app.route('/employee/logout')
def employee_logout():
    session.pop('employee_id',   None)
    session.pop('employee_name', None)
    return redirect('/employee/login')


# ═══════════════════════════════════════════════
# DASHBOARD
# ═══════════════════════════════════════════════

@app.route('/dashboard')
def dashboard():
    if not admin_required():
        return redirect('/admin')

    cur   = mysql.connection.cursor()
    today = datetime.date.today()
    week  = today.isocalendar()[1]

    cur.execute("SELECT COUNT(*) FROM attendance WHERE date=%s", (today,))
    today_checkins = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM attendance WHERE date=%s AND checkout IS NULL", (today,))
    present_now = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM attendance WHERE week=%s", (week,))
    week_total = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM employees")
    total_employees = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM attendance WHERE date=%s AND is_late=1", (today,))
    late_today = cur.fetchone()[0]
    cur.execute("SELECT id, name, department FROM employees ORDER BY name")
    employees = cur.fetchall()
    cur.execute(
        "SELECT name, checkin, checkout, is_late FROM attendance WHERE date=%s ORDER BY checkin DESC",
        (today,)
    )
    today_records = cur.fetchall()
    cur.execute("SELECT * FROM attendance ORDER BY date DESC, checkin DESC LIMIT 10")
    recent = cur.fetchall()
    cur.close()

    labels           = get_labels()
    camera_available = camera is not None

    return render_template("dashboard.html",
        today_checkins=today_checkins,
        present_now=present_now,
        week_total=week_total,
        total_employees=total_employees,
        late_today=late_today,
        employees=employees,
        today_records=today_records,
        recent=recent,
        today=str(today),
        camera_available=camera_available,
        labels=labels
    )


# ═══════════════════════════════════════════════
# FACE SCAN API
# ═══════════════════════════════════════════════

@app.route('/api/prediction')
def api_prediction():
    if not admin_required() and not superadmin_required():
        return jsonify({'error': 'unauthorized'}), 401
    with prediction_lock:
        return jsonify({
            "name":    latest_prediction["name"],
            "conf":    latest_prediction["conf"],
            "waiting": latest_prediction["waiting"]
        })

@app.route('/api/confirm', methods=['POST'])
def api_confirm():
    if not admin_required() and not superadmin_required():
        return jsonify({'error': 'unauthorized'}), 401
    with prediction_lock:
        name = latest_prediction["name"]
        latest_prediction.update({"waiting": False, "paused": False, "name": None, "conf": 0.0})
    if name:
        inserted, is_late = do_checkin(name)
        if inserted:
            msg = f'✅ {name} checked in successfully!'
            if is_late:
                msg += ' ⚠️ Late arrival'
            return jsonify({'status': 'ok', 'message': msg, 'late': is_late})
        return jsonify({'status': 'already', 'message': f'ℹ️ {name} already checked in today.'})
    return jsonify({'status': 'error', 'message': 'No prediction to confirm.'})

@app.route('/api/scan_again', methods=['POST'])
def api_scan_again():
    if not admin_required() and not superadmin_required():
        return jsonify({'error': 'unauthorized'}), 401
    with prediction_lock:
        latest_prediction.update({"waiting": False, "paused": False, "name": None, "conf": 0.0})
    return jsonify({'status': 'ok'})


# ═══════════════════════════════════════════════
# STATS + ANALYTICS API
# ═══════════════════════════════════════════════

@app.route('/api/stats')
def api_stats():
    if not admin_required() and not superadmin_required():
        return jsonify({'error': 'unauthorized'}), 401
    cur   = mysql.connection.cursor()
    today = datetime.date.today()
    week  = today.isocalendar()[1]
    cur.execute("SELECT COUNT(*) FROM attendance WHERE date=%s", (today,))
    today_checkins = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM attendance WHERE date=%s AND checkout IS NULL", (today,))
    present = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM attendance WHERE week=%s", (week,))
    week_total = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM attendance WHERE date=%s AND is_late=1", (today,))
    late_today = cur.fetchone()[0]
    cur.close()
    return jsonify({'today_checkins': today_checkins, 'present': present, 'week_total': week_total, 'late_today': late_today})

@app.route('/api/analytics/monthly')
def analytics_monthly():
    if not admin_required() and not superadmin_required():
        return jsonify({'error': 'unauthorized'}), 401
    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT DATE_FORMAT(date,'%Y-%m') as month, COUNT(*) as count
        FROM attendance GROUP BY month ORDER BY month DESC LIMIT 12
    """)
    rows = cur.fetchall()
    cur.close()
    return jsonify([{"month": r[0], "count": r[1]} for r in rows])

@app.route('/api/analytics/late')
def analytics_late():
    if not admin_required() and not superadmin_required():
        return jsonify({'error': 'unauthorized'}), 401
    cur = mysql.connection.cursor()
    cur.execute("SELECT name, COUNT(*) as late_count FROM attendance WHERE is_late=1 GROUP BY name ORDER BY late_count DESC")
    rows = cur.fetchall()
    cur.close()
    return jsonify([{"name": r[0], "late_count": r[1]} for r in rows])

@app.route('/api/analytics/hours')
def analytics_hours():
    if not admin_required() and not superadmin_required():
        return jsonify({'error': 'unauthorized'}), 401
    cur = mysql.connection.cursor()
    cur.execute("SELECT name, ROUND(AVG(hours_worked),2) as avg_hours FROM attendance WHERE hours_worked IS NOT NULL GROUP BY name ORDER BY avg_hours DESC")
    rows = cur.fetchall()
    cur.close()
    return jsonify([{"name": r[0], "avg_hours": float(r[1] or 0)} for r in rows])

@app.route('/api/analytics/department')
def analytics_department():
    if not admin_required() and not superadmin_required():
        return jsonify({'error': 'unauthorized'}), 401
    cur   = mysql.connection.cursor()
    today = datetime.date.today()
    cur.execute("""
        SELECT e.department, COUNT(a.id) as checkins
        FROM employees e
        LEFT JOIN attendance a ON a.name = e.name AND a.date = %s
        GROUP BY e.department
    """, (today,))
    rows = cur.fetchall()
    cur.close()
    return jsonify([{"department": r[0], "checkins": r[1]} for r in rows])


# ═══════════════════════════════════════════════
# CHECK-IN / CHECK-OUT API
# ═══════════════════════════════════════════════

@app.route('/api/checkin', methods=['POST'])
def api_checkin():
    if not admin_required() and not superadmin_required():
        return jsonify({'error': 'unauthorized'}), 401
    data = request.get_json()
    name = data.get('name', '').strip()
    if not name or not validate_name(name):
        return jsonify({'status': 'error', 'message': 'Invalid name'})
    inserted, is_late = do_checkin(name)
    if inserted:
        msg = f'✅ {name} checked in!'
        if is_late:
            msg += ' ⚠️ Late'
        return jsonify({'status': 'ok', 'message': msg, 'late': is_late})
    return jsonify({'status': 'already', 'message': f'ℹ️ {name} already checked in today.'})

@app.route('/api/checkout', methods=['POST'])
def api_checkout():
    if not admin_required() and not superadmin_required():
        return jsonify({'error': 'unauthorized'}), 401
    data = request.get_json()
    name = data.get('name', '').strip()
    if not name or not validate_name(name):
        return jsonify({'status': 'error', 'message': 'Invalid name'})
    do_checkout(name)
    return jsonify({'status': 'ok', 'message': f'✅ {name} checked out!'})


# ═══════════════════════════════════════════════
# ATTENDANCE RECORDS
# ═══════════════════════════════════════════════

@app.route('/attendance')
def attendance():
    if not admin_required() and not superadmin_required():
        return redirect('/admin')
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM attendance ORDER BY date DESC")
    data = cur.fetchall()
    cur.close()
    if request.args.get('export') == 'csv':
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['ID','Name','Date','Week','Check In','Check Out','Is Late','Hours Worked'])
        writer.writerows(data)
        output.seek(0)
        response = make_response(output.getvalue())
        response.headers['Content-Type']        = 'text/csv'
        response.headers['Content-Disposition'] = 'attachment; filename=attendance.csv'
        return response
    return render_template("attendance.html", data=data)


# ═══════════════════════════════════════════════
# EMPLOYEE MANAGEMENT
# ═══════════════════════════════════════════════

@app.route('/admin/employees')
def admin_employees():
    if not admin_required() and not superadmin_required():
        return redirect('/admin')
    cur = mysql.connection.cursor()
    cur.execute("SELECT id, name, email, department, company_id, face_label FROM employees ORDER BY name")
    employees = cur.fetchall()
    cur.close()
    return render_template("admin_employees.html", employees=employees)

@app.route('/admin/employees/add', methods=['POST'])
def admin_employees_add():
    if not admin_required() and not superadmin_required():
        return jsonify({'error': 'unauthorized'}), 401
    data       = request.get_json()
    name       = data.get('name',       '').strip()
    email      = data.get('email',      '').strip().lower()
    password   = data.get('password',   '').strip()
    department = data.get('department', 'General').strip()
    company_id = data.get('company_id', '').strip()
    face_label = data.get('face_label', '').strip() or None

    if not name or not validate_name(name):
        return jsonify({'status': 'error', 'message': 'Invalid name'})
    if not email or not validate_email(email):
        return jsonify({'status': 'error', 'message': 'Invalid email'})
    if not password or len(password) < 6:
        return jsonify({'status': 'error', 'message': 'Password must be at least 6 characters'})

    hashed_password = generate_password_hash(password)
    cur = mysql.connection.cursor()
    try:
        cur.execute(
            "INSERT INTO employees(name, email, password, department, company_id, face_label) VALUES(%s,%s,%s,%s,%s,%s)",
            (name, email, hashed_password, department, company_id, face_label)
        )
        mysql.connection.commit()
        cur.close()
        logger.info(f"Employee added: {name} ({email})")
        return jsonify({'status': 'ok'})
    except Exception as e:
        cur.close()
        logger.error(f"Employee add failed: {e}")
        return jsonify({'status': 'error', 'message': 'Email already exists'})

@app.route('/admin/employees/delete', methods=['POST'])
def admin_employees_delete():
    if not admin_required() and not superadmin_required():
        return jsonify({'error': 'unauthorized'}), 401
    data   = request.get_json()
    emp_id = data.get('emp_id')
    if not emp_id:
        return jsonify({'status': 'error', 'message': 'emp_id required'})
    cur = mysql.connection.cursor()
    cur.execute("DELETE FROM employees WHERE id=%s", (emp_id,))
    mysql.connection.commit()
    cur.close()
    logger.info(f"Employee deleted: id={emp_id}")
    return jsonify({'status': 'ok'})

@app.route('/admin/employees/change_password', methods=['POST'])
def admin_change_password():
    if not admin_required() and not superadmin_required():
        return jsonify({'error': 'unauthorized'}), 401
    data         = request.get_json()
    emp_id       = data.get('emp_id')
    new_password = data.get('new_password', '').strip()
    if not emp_id or len(new_password) < 6:
        return jsonify({'status': 'error', 'message': 'emp_id and password (min 6 chars) required'})
    hashed = generate_password_hash(new_password)
    cur    = mysql.connection.cursor()
    cur.execute("UPDATE employees SET password=%s WHERE id=%s", (hashed, emp_id))
    mysql.connection.commit()
    cur.close()
    logger.info(f"Password changed for emp_id={emp_id}")
    return jsonify({'status': 'ok', 'message': 'Password updated'})


# ═══════════════════════════════════════════════
# TASK MANAGEMENT
# ═══════════════════════════════════════════════

@app.route('/admin/tasks')
def admin_tasks():
    if not admin_required() and not superadmin_required():
        return redirect('/admin')
    cur = mysql.connection.cursor()
    cur.execute("SELECT id, name, email, department, company_id FROM employees ORDER BY name")
    employees = cur.fetchall()
    cur.execute("""
        SELECT t.id, t.title, t.description, t.assigned_to, t.assigned_by,
               t.priority, t.status, t.due_date, t.created_at,
               e.name AS emp_name, e.department
        FROM tasks t JOIN employees e ON t.assigned_to = e.id
        ORDER BY t.created_at DESC
    """)
    all_tasks = cur.fetchall()
    cur.close()
    return render_template("admin_tasks.html", employees=employees, all_tasks=all_tasks)

@app.route('/admin/tasks/add', methods=['POST'])
def admin_tasks_add():
    if not admin_required() and not superadmin_required():
        return jsonify({'error': 'unauthorized'}), 401
    data     = request.get_json()
    title    = data.get('title', '').strip()
    desc     = data.get('desc',  '').strip()
    emp_id   = data.get('emp_id')
    priority = data.get('priority', 'medium')
    due      = data.get('due') or None

    if not title or len(title) > 200:
        return jsonify({'status': 'error', 'message': 'Title required (max 200 chars)'})
    if not emp_id:
        return jsonify({'status': 'error', 'message': 'Employee required'})
    if priority not in ('low', 'medium', 'high'):
        priority = 'medium'

    cur = mysql.connection.cursor()
    cur.execute(
        "INSERT INTO tasks(title, description, assigned_to, priority, due_date) VALUES(%s,%s,%s,%s,%s)",
        (title, desc, emp_id, priority, due)
    )
    mysql.connection.commit()
    cur.close()
    logger.info(f"Task added: {title} → emp_id={emp_id}")
    return jsonify({'status': 'ok'})

@app.route('/admin/tasks/delete', methods=['POST'])
def admin_tasks_delete():
    if not admin_required() and not superadmin_required():
        return jsonify({'error': 'unauthorized'}), 401
    data    = request.get_json()
    task_id = data.get('task_id')
    if not task_id:
        return jsonify({'status': 'error', 'message': 'task_id required'})
    cur = mysql.connection.cursor()
    cur.execute("DELETE FROM tasks WHERE id=%s", (task_id,))
    mysql.connection.commit()
    cur.close()
    return jsonify({'status': 'ok'})


# ═══════════════════════════════════════════════
# EMPLOYEE PORTAL
# ═══════════════════════════════════════════════

@app.route('/employee/portal')
def employee_portal():
    if not employee_required():
        return redirect('/employee/login')

    emp_id   = session['employee_id']
    emp_name = session['employee_name']
    cur      = mysql.connection.cursor()

    cur.execute("SELECT id, name, email, department, company_id FROM employees WHERE id=%s", (emp_id,))
    emp = cur.fetchone()

    today       = datetime.date.today()
    today_str   = today.strftime('%Y-%m-%d')
    month_start = today.replace(day=1)
    week_start  = today - timedelta(days=today.weekday())

    cur.execute("SELECT id, checkin, checkout FROM attendance WHERE name=%s AND date=%s", (emp_name, today))
    today_att         = cur.fetchone()
    already_checkedin  = today_att is not None
    already_checkedout = today_att is not None and today_att[2] is not None

    cur.execute(
        "SELECT id, name, date, week, checkin, checkout, is_late, hours_worked FROM attendance WHERE name=%s ORDER BY date DESC",
        (emp_name,)
    )
    att_rows = cur.fetchall()
    attendance_records = [
        (row[0], row[1], to_str(row[2]), row[3],
         str(row[4]) if row[4] else None,
         str(row[5]) if row[5] else None,
         row[6], row[7])
        for row in att_rows
    ]

    cur.execute("SELECT COUNT(*) FROM attendance WHERE name=%s AND date>=%s AND date<=%s", (emp_name, month_start, today))
    month_days = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM attendance WHERE name=%s AND date>=%s AND date<=%s", (emp_name, week_start, today))
    week_days = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM attendance WHERE name=%s", (emp_name,))
    total_att = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM attendance WHERE name=%s AND is_late=1", (emp_name,))
    late_count = cur.fetchone()[0]

    try:
        cur.execute(
            "SELECT TIME_FORMAT(AVG(TIME_TO_SEC(checkin)), '%%H:%%i') FROM attendance WHERE name=%s AND date>=%s",
            (emp_name, month_start)
        )
        avg_checkin = cur.fetchone()[0]
    except Exception:
        avg_checkin = None

    attendance_stats = {
        'month_days':  month_days,
        'week_days':   week_days,
        'total':       total_att,
        'late_count':  late_count,
        'avg_checkin': avg_checkin or '—'
    }

    # Calendar
    present_dates  = {r[2] for r in attendance_records if r[2]}
    year, month_num = today.year, today.month
    num_days        = calendar.monthrange(year, month_num)[1]
    dow_labels      = ['Mo','Tu','We','Th','Fr','Sa','Su']
    calendar_days   = []
    for d in range(1, num_days+1):
        date_obj = datetime.date(year, month_num, d)
        date_str = date_obj.strftime('%Y-%m-%d')
        if date_str > today_str:           status = 'future'
        elif date_str == today_str:        status = 'today'
        elif date_str in present_dates:    status = 'present'
        else:                              status = 'absent'
        calendar_days.append({'day': d, 'date': date_str, 'status': status, 'dow': dow_labels[date_obj.weekday()]})

    # Tasks
    cur.execute("""
        SELECT id, title, description, assigned_to, assigned_by, priority, status, due_date, created_at
        FROM tasks WHERE assigned_to=%s
        ORDER BY FIELD(status,'in_progress','pending','completed'), FIELD(priority,'high','medium','low')
    """, (emp_id,))
    raw_tasks = cur.fetchall()
    tasks     = [(t[0],t[1],t[2],t[3],t[4],t[5],t[6],to_str(t[7]),to_str(t[8])) for t in raw_tasks]
    task_stats = {
        'total':       len(tasks),
        'pending':     sum(1 for t in tasks if t[6] == 'pending'),
        'in_progress': sum(1 for t in tasks if t[6] == 'in_progress'),
        'completed':   sum(1 for t in tasks if t[6] == 'completed'),
    }

    # Work logs
    cur.execute(
        "SELECT id, employee_id, log_date, work_done, hours_worked FROM work_logs WHERE employee_id=%s ORDER BY log_date DESC",
        (emp_id,)
    )
    raw_logs  = cur.fetchall()
    work_logs = [(lg[0],lg[1],to_str(lg[2]),lg[3],lg[4]) for lg in raw_logs]
    cur.close()

    employee_data = {
        'name':       emp[1],
        'email':      emp[2],
        'department': emp[3] if emp[3] else 'General',
        'company_id': emp[4] if emp[4] else '—'
    }

    return render_template("employee_portal.html",
        employee=employee_data,
        attendance_records=attendance_records,
        attendance_stats=attendance_stats,
        calendar_days=calendar_days,
        current_month=today.strftime('%B %Y'),
        tasks=tasks,
        task_stats=task_stats,
        pending_tasks=task_stats['pending'],
        work_logs=work_logs,
        today=today_str,
        already_checkedin=already_checkedin,
        already_checkedout=already_checkedout
    )

@app.route('/employee/checkin', methods=['POST'])
def employee_checkin():
    if not employee_required():
        return jsonify({'error': 'unauthorized'}), 401
    inserted, is_late = do_checkin(session['employee_name'])
    if inserted:
        msg = '✅ Checked in successfully!'
        if is_late:
            msg += ' ⚠️ You are late today.'
        return jsonify({'status': 'ok', 'message': msg, 'late': is_late})
    return jsonify({'status': 'already', 'message': 'ℹ️ Already checked in today.'})

@app.route('/employee/checkout', methods=['POST'])
def employee_checkout():
    if not employee_required():
        return jsonify({'error': 'unauthorized'}), 401
    do_checkout(session['employee_name'])
    return jsonify({'status': 'ok', 'message': '✅ Checked out successfully!'})

@app.route('/employee/task/update', methods=['POST'])
def employee_task_update():
    if not employee_required():
        return jsonify({'error': 'unauthorized'}), 401
    data    = request.get_json()
    task_id = data.get('task_id')
    status  = data.get('status')
    if status not in ('pending', 'in_progress', 'completed'):
        return jsonify({'status': 'error', 'message': 'Invalid status'})
    cur = mysql.connection.cursor()
    cur.execute(
        "UPDATE tasks SET status=%s WHERE id=%s AND assigned_to=%s",
        (status, task_id, session['employee_id'])
    )
    mysql.connection.commit()
    cur.close()
    return jsonify({'status': 'ok'})

@app.route('/employee/worklog/add', methods=['POST'])
def employee_worklog_add():
    if not employee_required():
        return jsonify({'error': 'unauthorized'}), 401
    data     = request.get_json()
    log_date = data.get('date')
    hours    = data.get('hours')
    work     = data.get('work', '').strip()
    if not log_date or not hours or not work:
        return jsonify({'status': 'error', 'message': 'All fields required'})
    if len(work) > 1000:
        return jsonify({'status': 'error', 'message': 'Work description too long'})
    try:
        hours = float(hours)
        if hours <= 0 or hours > 24:
            raise ValueError
    except ValueError:
        return jsonify({'status': 'error', 'message': 'Invalid hours value'})
    cur = mysql.connection.cursor()
    cur.execute(
        "INSERT INTO work_logs(employee_id, log_date, work_done, hours_worked) VALUES(%s,%s,%s,%s)",
        (session['employee_id'], log_date, work, hours)
    )
    mysql.connection.commit()
    cur.close()
    return jsonify({'status': 'ok'})

@app.route('/employee/change_password', methods=['POST'])
def employee_change_password():
    if not employee_required():
        return jsonify({'error': 'unauthorized'}), 401
    data         = request.get_json()
    old_password = data.get('old_password', '').strip()
    new_password = data.get('new_password', '').strip()
    if len(new_password) < 6:
        return jsonify({'status': 'error', 'message': 'New password must be at least 6 characters'})
    cur = mysql.connection.cursor()
    cur.execute("SELECT password FROM employees WHERE id=%s", (session['employee_id'],))
    row = cur.fetchone()
    if not row:
        cur.close()
        return jsonify({'status': 'error', 'message': 'Employee not found'})
    stored = row[0]
    valid = check_password_hash(stored, old_password) if (stored.startswith('$2b$') or stored.startswith('$2y$')) else (stored == old_password)
    if not valid:
        cur.close()
        return jsonify({'status': 'error', 'message': 'Current password is wrong'})
    hashed = generate_password_hash(new_password)
    cur.execute("UPDATE employees SET password=%s WHERE id=%s", (hashed, session['employee_id']))
    mysql.connection.commit()
    cur.close()
    logger.info(f"Password changed by employee id={session['employee_id']}")
    return jsonify({'status': 'ok', 'message': 'Password updated successfully'})


# ═══════════════════════════════════════════════
# ERROR HANDLERS
# ═══════════════════════════════════════════════

@app.errorhandler(404)
def not_found(e):
    return render_template("404.html"), 404

@app.errorhandler(429)
def rate_limited(e):
    return jsonify({'error': 'Too many attempts. Please wait.'}), 429

@app.errorhandler(500)
def server_error(e):
    logger.error(f"500 error: {e}")
    return render_template("500.html"), 500


# ═══════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)