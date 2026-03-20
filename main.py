from flask import Flask, render_template, Response, request, redirect, session, jsonify, make_response
from flask_mysqldb import MySQL
import cv2
try:
    import tensorflow as tf
except:
tf = None

import numpy as npimport datetime
from datetime import timedelta
import calendar
import csv
import io
import os
import threading
import time
from datetime import datetime

updated_at = datetime.now()

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'attendance_secret_key_2024')
app.config['SESSION_PERMANENT'] = True
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=8)

UPLOAD_FOLDER = os.path.join('static', 'proof_uploads')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf'}
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024

app.config['MYSQL_HOST']     = os.environ.get('MYSQLHOST',     'localhost')
app.config['MYSQL_USER']     = os.environ.get('MYSQLUSER',     'root')
app.config['MYSQL_PASSWORD'] = os.environ.get('MYSQLPASSWORD', 'Mohith@123')
app.config['MYSQL_DB']       = os.environ.get('MYSQLDATABASE', 'attendance_system')
app.config['MYSQL_PORT']     = int(os.environ.get('MYSQLPORT', 3306))

mysql = MySQL(app)

if tf:
    model = tf.keras.models.load_model("model/face_model4.keras")
else:
   model = None

face_cascade = cv2.CascadeClassifier(
    cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
)

labels = ["DIVYADHAR", "Mohith", "Uday"]

DEPARTMENTS = ['Development', 'HR', 'Design', 'Operations', 'Marketing', 'Research', 'Cybersecurity']

camera = None
print("Camera disabled on server")

latest_prediction = {"name": None, "conf": 0.0, "waiting": False, "paused": False}
prediction_lock = threading.Lock()
last_frame = None


# ── HELPERS ───────────────────────────────────────────────────────────────────
def admin_required():
    return 'admin' in session

def superadmin_required():
    return 'superadmin' in session

def employee_required():
    return 'employee_id' in session

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def to_str(val):
    if val is None: return None
    if isinstance(val, (datetime.date, datetime.datetime)):
        return val.strftime('%Y-%m-%d')
    return str(val)

def do_checkin(name):
    cur = mysql.connection.cursor()
    today = datetime.date.today()
    week = today.isocalendar()[1]
    cur.execute("SELECT id FROM attendance WHERE name=%s AND date=%s", (name, today))
    if cur.fetchone() is None:
        now = datetime.datetime.now().time()
        cur.execute("INSERT INTO attendance(name, date, week, checkin) VALUES(%s,%s,%s,%s)",
                    (name, today, week, now))
        mysql.connection.commit()
        cur.close()
        return True
    cur.close()
    return False

def do_checkout(name):
    cur = mysql.connection.cursor()
    today = datetime.date.today()
    now = datetime.datetime.now().time()
    cur.execute("UPDATE attendance SET checkout=%s WHERE name=%s AND date=%s", (now, name, today))
    mysql.connection.commit()
    cur.close()

def get_admin_department():
    return session.get('admin_department', None)


# ── CAMERA ────────────────────────────────────────────────────────────────────
def frames():
    global last_frame
    last_detect_time = 0
    COOLDOWN = 5
    THRESHOLD = 0.92
    MIN_FACE_SIZE = 80
    DEBUG = True

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
        success, frame = camera.read()
        if not success or frame is None:
            time.sleep(0.1)
            continue

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(gray, 1.3, 5)
        now_ts = time.time()

        for (x, y, w, h) in faces:
            if w < MIN_FACE_SIZE or h < MIN_FACE_SIZE:
                cv2.rectangle(frame, (x,y), (x+w,y+h), (128,128,128), 1)
                continue
            roi = frame[y:y+h, x:x+w]
            img_r = cv2.resize(roi, (128,128)) / 255.0
            img_r = np.reshape(img_r, (1,128,128,3))
           if model:
    pred = model.predict(img_r)
else:
    continue
            label_idx = int(np.argmax(pred))
            conf = float(np.max(pred))

            if conf >= THRESHOLD:
                name = labels[label_idx]
                gray_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
                blur_score = cv2.Laplacian(gray_roi, cv2.CV_64F).var()
                texture_score = float(np.std(cv2.resize(gray_roi, (32,32))))
                mean_brightness = float(np.mean(roi))
                if DEBUG:
                    print(f"[{name}] conf={conf:.2f} blur={blur_score:.1f} tex={texture_score:.1f} bright={mean_brightness:.1f}")
                is_live = blur_score < 800 and texture_score > 15 and mean_brightness < 225
                if is_live:
                    color = (0,255,0)
                    with prediction_lock:
                        already_waiting = latest_prediction["waiting"]
                    if not already_waiting and (now_ts - last_detect_time) > COOLDOWN:
                        with prediction_lock:
                            latest_prediction.update({"name": name, "conf": round(conf*100,1), "waiting": True, "paused": True})
                        last_detect_time = now_ts
                else:
                    name = "SPOOF"; color = (0,165,255)
            else:
                name = "Unknown"; color = (0,0,255)

            cv2.rectangle(frame, (x,y), (x+w,y+h), color, 2)
            cv2.putText(frame, f"{name} ({conf:.0%})", (x,y-10), cv2.FONT_HERSHEY_SIMPLEX, 0.75, color, 2)

        ret, buffer = cv2.imencode('.jpg', frame)
        if not ret: continue
        frame_bytes = buffer.tobytes()
        last_frame = frame_bytes
        yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')


# ══════════════════════════════════════════════════════════════════════════════
# PUBLIC
# ══════════════════════════════════════════════════════════════════════════════

@app.route('/')
def index():
    return render_template("index.html")


# ══════════════════════════════════════════════════════════════════════════════
# SUPER ADMIN ROUTES
# ══════════════════════════════════════════════════════════════════════════════

@app.route('/superadmin', methods=['GET', 'POST'])
def superadmin_login():
    if superadmin_required():
        return redirect('/superadmin/dashboard')
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '').strip()
        cur = mysql.connection.cursor()
        cur.execute("SELECT * FROM super_admin WHERE email=%s AND password=%s", (email, password))
        sa = cur.fetchone()
        cur.close()
        if sa:
            session['superadmin'] = True
            session['superadmin_email'] = email
            session['superadmin_name'] = sa[3] if sa[3] else 'Super Admin'
            return redirect('/superadmin/dashboard')
        return render_template("superadmin_login.html", error=True)
    return render_template("superadmin_login.html")


@app.route('/superadmin/dashboard')
def superadmin_dashboard():
    if not superadmin_required():
        return redirect('/superadmin')
    cur = mysql.connection.cursor()
    today = datetime.date.today()
    week = today.isocalendar()[1]

    # Company-wide stats
    cur.execute("SELECT COUNT(*) FROM employees")
    total_employees = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM attendance WHERE date=%s", (today,))
    today_checkins = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM tasks")
    total_tasks = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM tasks WHERE status='completed'")
    completed_tasks = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM tasks WHERE status='proof_submitted' AND admin_verdict='pending'")
    pending_proofs = cur.fetchone()[0]

    # Department-wise stats
    cur.execute("""
        SELECT e.department, COUNT(e.id) as emp_count,
               COUNT(a.id) as present_today
        FROM employees e
        LEFT JOIN attendance a ON a.name=e.name AND a.date=%s
        GROUP BY e.department
        ORDER BY e.department
    """, (today,))
    dept_stats = cur.fetchall()

    # All tasks with employee + dept info (including dept-only tasks from super admin)
    cur.execute("""
        SELECT t.id, t.title, t.description, t.priority, t.status,
               t.due_date, t.created_at,
               COALESCE(e.name, '— Unassigned —') as emp_name,
               COALESCE(e.department, t.assigned_dept) as dept,
               t.proof_submitted_at, t.admin_verdict, t.assigned_dept,
               COALESCE(t.assigned_to, 0) as emp_id
        FROM tasks t LEFT JOIN employees e ON t.assigned_to=e.id
        ORDER BY t.created_at DESC
    """)
    all_tasks = cur.fetchall()
    tasks_clean = [(t[0],t[1],t[2],t[3],t[4],to_str(t[5]),to_str(t[6]),t[7],t[8],to_str(t[9]),t[10],t[11],t[12]) for t in all_tasks]

    # All attendance today
    cur.execute("""
        SELECT a.name, a.checkin, a.checkout, e.department
        FROM attendance a
        LEFT JOIN employees e ON e.name=a.name
        WHERE a.date=%s ORDER BY a.checkin DESC
    """, (today,))
    today_attendance = cur.fetchall()

    # All dept admins
    cur.execute("SELECT id, username, department, email FROM admin ORDER BY department")
    dept_admins = cur.fetchall()

    # All employees
    cur.execute("SELECT id, name, email, department FROM employees ORDER BY department, name")
    all_employees = cur.fetchall()

    cur.close()
    return render_template("superadmin_dashboard.html",
        total_employees=total_employees,
        today_checkins=today_checkins,
        total_tasks=total_tasks,
        completed_tasks=completed_tasks,
        pending_proofs=pending_proofs,
        dept_stats=dept_stats,
        all_tasks=tasks_clean,
        today_attendance=today_attendance,
        dept_admins=dept_admins,
        all_employees=all_employees,
        departments=DEPARTMENTS,
        today=str(today),
        superadmin_name=session.get('superadmin_name', 'Super Admin')
    )


@app.route('/superadmin/tasks/add', methods=['POST'])
def superadmin_tasks_add():
    if not superadmin_required():
        return jsonify({'error': 'unauthorized'}), 401
    data = request.get_json()
    title = data.get('title', '').strip()
    desc = data.get('desc', '').strip()
    emp_id = data.get('emp_id') or None      # optional
    dept = data.get('dept', '').strip()       # required
    priority = data.get('priority', 'medium')
    due = data.get('due') or None
    if not title or not dept:
        return jsonify({'status': 'error', 'message': 'Title and department required'})
    cur = mysql.connection.cursor()
    cur.execute(
        "INSERT INTO tasks(title, description, assigned_to, assigned_dept, assigned_by, priority, due_date) VALUES(%s,%s,%s,%s,%s,%s,%s)",
        (title, desc, emp_id, dept, 'Super Admin', priority, due)
    )
    mysql.connection.commit()
    cur.close()
    return jsonify({'status': 'ok'})


@app.route('/superadmin/tasks/delete', methods=['POST'])
def superadmin_tasks_delete():
    if not superadmin_required():
        return jsonify({'error': 'unauthorized'}), 401
    data = request.get_json()
    task_id = data.get('task_id')
    cur = mysql.connection.cursor()
    cur.execute("DELETE FROM tasks WHERE id=%s", (task_id,))
    mysql.connection.commit()
    cur.close()
    return jsonify({'status': 'ok'})


@app.route('/superadmin/admins/add', methods=['POST'])
def superadmin_admins_add():
    if not superadmin_required():
        return jsonify({'error': 'unauthorized'}), 401
    data = request.get_json()
    email = data.get('email', '').strip().lower()
    password = data.get('password', '').strip()
    department = data.get('department', '').strip()
    if not email or not password or not department:
        return jsonify({'status': 'error', 'message': 'All fields required'})
    cur = mysql.connection.cursor()
    try:
        cur.execute(
            "INSERT INTO admin(username, password, department, email) VALUES(%s,%s,%s,%s)",
            (email, password, department, email)
        )
        mysql.connection.commit()
        cur.close()
        return jsonify({'status': 'ok'})
    except Exception as e:
        cur.close()
        return jsonify({'status': 'error', 'message': 'Email already exists'})


@app.route('/superadmin/admins/delete', methods=['POST'])
def superadmin_admins_delete():
    if not superadmin_required():
        return jsonify({'error': 'unauthorized'}), 401
    data = request.get_json()
    admin_id = data.get('admin_id')
    if not admin_id:
        return jsonify({'status': 'error', 'message': 'No admin_id provided'})
    try:
        admin_id = int(admin_id)
    except (ValueError, TypeError):
        return jsonify({'status': 'error', 'message': 'Invalid admin_id'})
    cur = mysql.connection.cursor()
    cur.execute("DELETE FROM admin WHERE id=%s", (admin_id,))
    affected = cur.rowcount
    mysql.connection.commit()
    cur.close()
    if affected == 0:
        return jsonify({'status': 'error', 'message': 'Admin not found'})
    return jsonify({'status': 'ok'})


@app.route('/superadmin/employees/assign_dept', methods=['POST'])
def superadmin_assign_dept():
    if not superadmin_required():
        return jsonify({'error': 'unauthorized'}), 401
    data = request.get_json()
    emp_id = data.get('emp_id')
    department = data.get('department', '').strip()
    if not emp_id or not department:
        return jsonify({'status': 'error', 'message': 'Employee and department required'})
    cur = mysql.connection.cursor()
    cur.execute("UPDATE employees SET department=%s WHERE id=%s", (department, emp_id))
    mysql.connection.commit()
    cur.close()
    return jsonify({'status': 'ok'})


@app.route('/superadmin/employees/bulk_assign_dept', methods=['POST'])
def superadmin_bulk_assign_dept():
    if not superadmin_required():
        return jsonify({'error': 'unauthorized'}), 401
    data = request.get_json()
    emp_ids = data.get('emp_ids', [])
    department = data.get('department', '').strip()
    if not emp_ids or not department:
        return jsonify({'status': 'error', 'message': 'Employees and department required'})
    cur = mysql.connection.cursor()
    for emp_id in emp_ids:
        cur.execute("UPDATE employees SET department=%s WHERE id=%s", (department, emp_id))
    mysql.connection.commit()
    cur.close()
    return jsonify({'status': 'ok'})


@app.route('/superadmin/api/employees_by_dept')
def superadmin_employees_by_dept():
    if not superadmin_required():
        return jsonify({'error': 'unauthorized'}), 401
    dept = request.args.get('dept', '')
    cur = mysql.connection.cursor()
    if dept:
        cur.execute("SELECT id, name, department FROM employees WHERE department=%s ORDER BY name", (dept,))
    else:
        cur.execute("SELECT id, name, department FROM employees ORDER BY department, name")
    employees = [{'id': r[0], 'name': r[1], 'dept': r[2]} for r in cur.fetchall()]
    cur.close()
    return jsonify(employees)


@app.route('/superadmin/logout')
def superadmin_logout():
    session.pop('superadmin', None)
    session.pop('superadmin_email', None)
    session.pop('superadmin_name', None)
    return redirect('/superadmin')


# ══════════════════════════════════════════════════════════════════════════════
# ADMIN ROUTES (dept-scoped)
# ══════════════════════════════════════════════════════════════════════════════

@app.route('/video')
def video():
    if not admin_required(): return "Unauthorized", 401
    if camera is None: return "No camera available", 503
    return Response(frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/api/prediction')
def api_prediction():
    if not admin_required(): return jsonify({'error': 'unauthorized'}), 401
    with prediction_lock:
        return jsonify({"name": latest_prediction["name"], "conf": latest_prediction["conf"], "waiting": latest_prediction["waiting"]})

@app.route('/api/confirm', methods=['POST'])
def api_confirm():
    if not admin_required(): return jsonify({'error': 'unauthorized'}), 401
    with prediction_lock:
        name = latest_prediction["name"]
        latest_prediction.update({"waiting": False, "paused": False, "name": None, "conf": 0.0})
    if name:
        inserted = do_checkin(name)
        if inserted:
            return jsonify({'status': 'ok', 'message': f'✅ {name} checked in successfully!'})
        return jsonify({'status': 'already', 'message': f'ℹ️ {name} already checked in today.'})
    return jsonify({'status': 'error', 'message': 'No prediction to confirm.'})

@app.route('/api/scan_again', methods=['POST'])
def api_scan_again():
    if not admin_required(): return jsonify({'error': 'unauthorized'}), 401
    with prediction_lock:
        latest_prediction.update({"waiting": False, "paused": False, "name": None, "conf": 0.0})
    return jsonify({'status': 'ok'})

@app.route('/api/stats')
def api_stats():
    if not admin_required(): return jsonify({'error': 'unauthorized'}), 401
    cur = mysql.connection.cursor()
    today = datetime.date.today()
    week = today.isocalendar()[1]
    dept = get_admin_department()
    if dept:
        cur.execute("SELECT COUNT(*) FROM attendance a JOIN employees e ON e.name=a.name WHERE a.date=%s AND e.department=%s", (today, dept))
        today_checkins = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM attendance a JOIN employees e ON e.name=a.name WHERE a.date=%s AND a.checkout IS NULL AND e.department=%s", (today, dept))
        present = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM attendance a JOIN employees e ON e.name=a.name WHERE a.week=%s AND e.department=%s", (week, dept))
        week_total = cur.fetchone()[0]
    else:
        cur.execute("SELECT COUNT(*) FROM attendance WHERE date=%s", (today,))
        today_checkins = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM attendance WHERE date=%s AND checkout IS NULL", (today,))
        present = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM attendance WHERE week=%s", (week,))
        week_total = cur.fetchone()[0]
    cur.close()
    return jsonify({'today_checkins': today_checkins, 'present': present, 'week_total': week_total})

@app.route('/api/checkin', methods=['POST'])
def api_checkin():
    if not admin_required(): return jsonify({'error': 'unauthorized'}), 401
    data = request.get_json()
    name = data.get('name', '').strip()
    if not name: return jsonify({'status': 'error', 'message': 'Name required'})
    inserted = do_checkin(name)
    if inserted: return jsonify({'status': 'ok', 'message': f'✅ {name} checked in!'})
    return jsonify({'status': 'already', 'message': f'ℹ️ {name} already checked in today.'})

@app.route('/api/checkout', methods=['POST'])
def api_checkout():
    if not admin_required(): return jsonify({'error': 'unauthorized'}), 401
    data = request.get_json()
    name = data.get('name', '').strip()
    if not name: return jsonify({'status': 'error', 'message': 'Name required'})
    do_checkout(name)
    return jsonify({'status': 'ok', 'message': f'✅ {name} checked out!'})

@app.route('/logout_employee/<n>')
def logout_employee(n):
    if not admin_required(): return "Unauthorized", 401
    do_checkout(n)
    return f"Checkout recorded for {n}", 200

@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if admin_required(): return redirect('/dashboard')
    if request.method == 'POST':
        email = request.form.get('username', '').strip().lower()
        password = request.form.get('password', '').strip()
        if not email or not password:
            return render_template("admin_login.html", error=True)
        cur = mysql.connection.cursor()
        cur.execute("SELECT id, username, password, department, email FROM admin WHERE (username=%s OR email=%s) AND password=%s", (email, email, password))
        admin_user = cur.fetchone()
        cur.close()
        if admin_user:
            session['admin'] = True
            session['admin_department'] = admin_user[3]
            session['admin_email'] = admin_user[4] or admin_user[1]
            return redirect('/dashboard')
        return render_template("admin_login.html", error=True)
    return render_template("admin_login.html")

@app.route('/dashboard')
def dashboard():
    if not admin_required(): return redirect('/admin')
    cur = mysql.connection.cursor()
    today = datetime.date.today()
    week = today.isocalendar()[1]
    dept = get_admin_department()

    # Scoped to department
    if dept:
        cur.execute("SELECT COUNT(*) FROM employees WHERE department=%s", (dept,))
        total_employees = cur.fetchone()[0]
        cur.execute("SELECT id, name, department FROM employees WHERE department=%s ORDER BY name", (dept,))
        employees = cur.fetchall()
        cur.execute("""SELECT COUNT(*) FROM attendance a JOIN employees e ON e.name=a.name
                       WHERE a.date=%s AND e.department=%s""", (today, dept))
        today_checkins = cur.fetchone()[0]
        cur.execute("""SELECT COUNT(*) FROM attendance a JOIN employees e ON e.name=a.name
                       WHERE a.date=%s AND a.checkout IS NULL AND e.department=%s""", (today, dept))
        present_now = cur.fetchone()[0]
        cur.execute("""SELECT COUNT(*) FROM attendance a JOIN employees e ON e.name=a.name
                       WHERE a.week=%s AND e.department=%s""", (week, dept))
        week_total = cur.fetchone()[0]
    else:
        cur.execute("SELECT COUNT(*) FROM employees")
        total_employees = cur.fetchone()[0]
        cur.execute("SELECT id, name, department FROM employees ORDER BY name")
        employees = cur.fetchall()
        cur.execute("SELECT COUNT(*) FROM attendance WHERE date=%s", (today,))
        today_checkins = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM attendance WHERE date=%s AND checkout IS NULL", (today,))
        present_now = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM attendance WHERE week=%s", (week,))
        week_total = cur.fetchone()[0]

    cur.execute("SELECT name, checkin, checkout FROM attendance WHERE date=%s ORDER BY checkin DESC", (today,))
    today_records = cur.fetchall()
    cur.execute("SELECT * FROM attendance ORDER BY date DESC, checkin DESC LIMIT 10")
    recent = cur.fetchall()
    cur.close()

    return render_template("dashboard.html",
        today_checkins=today_checkins, present_now=present_now,
        week_total=week_total, total_employees=total_employees,
        employees=employees, today_records=today_records,
        recent=recent, today=str(today),
        camera_available=camera is not None,
        labels=labels,
        admin_department=dept
    )

@app.route('/attendance')
def attendance():
    if not admin_required(): return redirect('/admin')
    cur = mysql.connection.cursor()
    dept = get_admin_department()
    if dept:
        cur.execute("""SELECT a.* FROM attendance a JOIN employees e ON e.name=a.name
                       WHERE e.department=%s ORDER BY a.date DESC""", (dept,))
    else:
        cur.execute("SELECT * FROM attendance ORDER BY date DESC")
    data = cur.fetchall()
    cur.close()
    if request.args.get('export') == 'csv':
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['ID', 'Name', 'Date', 'Week', 'Check In', 'Check Out'])
        writer.writerows(data)
        output.seek(0)
        response = make_response(output.getvalue())
        response.headers['Content-Type'] = 'text/csv'
        response.headers['Content-Disposition'] = 'attachment; filename=attendance.csv'
        return response
    return render_template("attendance.html", data=data)

@app.route('/logout')
def logout():
    session.pop('admin', None)
    session.pop('admin_department', None)
    session.pop('admin_email', None)
    return redirect('/admin')

@app.route('/admin/employees')
def admin_employees():
    if not admin_required(): return redirect('/admin')
    cur = mysql.connection.cursor()
    dept = get_admin_department()
    if dept:
        cur.execute("SELECT id, name, email, department, company_id FROM employees WHERE department=%s ORDER BY name", (dept,))
    else:
        cur.execute("SELECT id, name, email, department, company_id FROM employees ORDER BY name")
    employees = cur.fetchall()
    cur.close()
    return render_template("admin_employees.html", employees=employees)

@app.route('/admin/employees/add', methods=['POST'])
def admin_employees_add():
    if not admin_required(): return jsonify({'error': 'unauthorized'}), 401
    data = request.get_json()
    name = data.get('name', '').strip()
    email = data.get('email', '').strip().lower()
    password = data.get('password', '').strip()
    department = data.get('department', get_admin_department() or 'General').strip()
    company_id = data.get('company_id', '').strip()
    if not name or not email or not password:
        return jsonify({'status': 'error', 'message': 'Name, email and password required'})
    cur = mysql.connection.cursor()
    try:
        cur.execute("INSERT INTO employees(name, email, password, department, company_id) VALUES(%s,%s,%s,%s,%s)",
                    (name, email, password, department, company_id))
        mysql.connection.commit()
        cur.close()
        return jsonify({'status': 'ok'})
    except Exception:
        cur.close()
        return jsonify({'status': 'error', 'message': 'Email already exists'})

@app.route('/admin/employees/delete', methods=['POST'])
def admin_employees_delete():
    if not admin_required(): return jsonify({'error': 'unauthorized'}), 401
    data = request.get_json()
    emp_id = data.get('emp_id')
    cur = mysql.connection.cursor()
    cur.execute("DELETE FROM employees WHERE id=%s", (emp_id,))
    mysql.connection.commit()
    cur.close()
    return jsonify({'status': 'ok'})

@app.route('/admin/tasks')
def admin_tasks():
    if not admin_required(): return redirect('/admin')
    cur = mysql.connection.cursor()
    dept = get_admin_department()
    cur.execute("SELECT id, name, email, department, company_id FROM employees WHERE department=%s ORDER BY name" if dept else
                "SELECT id, name, email, department, company_id FROM employees ORDER BY name",
                (dept,) if dept else ())
    employees = cur.fetchall()

    if dept:
        cur.execute("""
            SELECT t.id, t.title, t.description, t.assigned_to, t.assigned_by,
                   t.priority, t.status, t.due_date, t.created_at,
                   e.name, e.department,
                   t.proof_text, t.proof_link, t.proof_image,
                   t.proof_submitted_at, t.admin_verdict, t.admin_note
            FROM tasks t JOIN employees e ON t.assigned_to=e.id
            WHERE e.department=%s ORDER BY t.created_at DESC
        """, (dept,))
    else:
        cur.execute("""
            SELECT t.id, t.title, t.description, t.assigned_to, t.assigned_by,
                   t.priority, t.status, t.due_date, t.created_at,
                   e.name, e.department,
                   t.proof_text, t.proof_link, t.proof_image,
                   t.proof_submitted_at, t.admin_verdict, t.admin_note
            FROM tasks t JOIN employees e ON t.assigned_to=e.id
            ORDER BY t.created_at DESC
        """)
    all_tasks = cur.fetchall()
    cur.execute("SELECT COUNT(*) FROM tasks t JOIN employees e ON t.assigned_to=e.id WHERE t.status='proof_submitted' AND t.admin_verdict='pending'" +
                (" AND e.department=%s" if dept else ""), (dept,) if dept else ())
    pending_proofs = cur.fetchone()[0]

    # Tasks from Super Admin assigned to this dept but not yet assigned to an employee
    if dept:
        cur.execute("""
            SELECT t.id, t.title, t.description, t.assigned_to, t.assigned_by,
                   t.priority, t.status, t.due_date, t.created_at,
                   t.assigned_dept
            FROM tasks t
            WHERE t.assigned_by='Super Admin' AND t.assigned_dept=%s
            ORDER BY t.created_at DESC
        """, (dept,))
    else:
        cur.execute("""
            SELECT t.id, t.title, t.description, t.assigned_to, t.assigned_by,
                   t.priority, t.status, t.due_date, t.created_at,
                   t.assigned_dept
            FROM tasks t
            WHERE t.assigned_by='Super Admin'
            ORDER BY t.created_at DESC
        """)
    sa_tasks_raw = cur.fetchall()

    # Super admin tasks with employee name if assigned
    sa_tasks = []
    for t in sa_tasks_raw:
        emp_name = None
        if t[3]:  # assigned_to exists
            cur.execute("SELECT name FROM employees WHERE id=%s", (t[3],))
            row = cur.fetchone()
            emp_name = row[0] if row else None
        sa_tasks.append((t[0],t[1],t[2],t[3],t[4],t[5],t[6],to_str(t[7]),to_str(t[8]),t[9],emp_name))

    cur.close()

    tasks_clean = []
    for t in all_tasks:
        tasks_clean.append(list(t[:8]) + [to_str(t[8])] + list(t[9:14]) + [to_str(t[14])] + list(t[15:]))

    return render_template("admin_tasks.html",
        employees=employees, all_tasks=tasks_clean,
        sa_tasks=sa_tasks,
        pending_proofs=pending_proofs,
        admin_department=dept
    )

@app.route('/admin/tasks/assign_sa_task', methods=['POST'])
def admin_assign_sa_task():
    if not admin_required(): return jsonify({'error': 'unauthorized'}), 401
    data = request.get_json()
    task_id = data.get('task_id')
    emp_id = data.get('emp_id')
    if not task_id or not emp_id:
        return jsonify({'status': 'error', 'message': 'Task and employee required'})
    cur = mysql.connection.cursor()
    cur.execute("UPDATE tasks SET assigned_to=%s WHERE id=%s", (emp_id, task_id))
    mysql.connection.commit()
    cur.close()
    return jsonify({'status': 'ok'})


@app.route('/admin/tasks/add', methods=['POST'])
def admin_tasks_add():
    if not admin_required(): return jsonify({'error': 'unauthorized'}), 401
    data = request.get_json()
    title = data.get('title', '').strip()
    desc = data.get('desc', '').strip()
    emp_id = data.get('emp_id')
    priority = data.get('priority', 'medium')
    due = data.get('due') or None
    if not title or not emp_id:
        return jsonify({'status': 'error', 'message': 'Title and employee required'})
    cur = mysql.connection.cursor()
    cur.execute("INSERT INTO tasks(title, description, assigned_to, priority, due_date) VALUES(%s,%s,%s,%s,%s)",
                (title, desc, emp_id, priority, due))
    mysql.connection.commit()
    cur.close()
    return jsonify({'status': 'ok'})

@app.route('/admin/tasks/delete', methods=['POST'])
def admin_tasks_delete():
    if not admin_required(): return jsonify({'error': 'unauthorized'}), 401
    data = request.get_json()
    task_id = data.get('task_id')
    cur = mysql.connection.cursor()
    cur.execute("DELETE FROM tasks WHERE id=%s", (task_id,))
    mysql.connection.commit()
    cur.close()
    return jsonify({'status': 'ok'})

@app.route('/admin/tasks/verdict', methods=['POST'])
def admin_tasks_verdict():
    if not admin_required(): return jsonify({'error': 'unauthorized'}), 401
    data = request.get_json()
    task_id = data.get('task_id')
    verdict = data.get('verdict')
    note = data.get('note', '').strip()
    if verdict not in ('approved', 'rejected'):
        return jsonify({'status': 'error'})
    cur = mysql.connection.cursor()
    new_status = 'completed' if verdict == 'approved' else 'in_progress'
    cur.execute("UPDATE tasks SET admin_verdict=%s, admin_note=%s, status=%s WHERE id=%s",
                (verdict, note, new_status, task_id))
    # Find who the task belongs to
    cur.execute("SELECT assigned_to, title FROM tasks WHERE id=%s", (task_id,))
    task = cur.fetchone()
    mysql.connection.commit()
    cur.close()
    if task and task[0]:
        emp_id = task[0]
        task_title = task[1] or 'task'
        if verdict == 'approved':
            update_performance(emp_id, 'proof_approved', f'Proof approved: {task_title}')
            update_performance(emp_id, 'task_completed', f'Task completed: {task_title}')
        else:
            update_performance(emp_id, 'proof_rejected', f'Proof rejected: {task_title}. {note}')
    return jsonify({'status': 'ok', 'verdict': verdict})


# ══════════════════════════════════════════════════════════════════════════════
# EMPLOYEE ROUTES
# ══════════════════════════════════════════════════════════════════════════════

@app.route('/employee/login', methods=['GET', 'POST'])
def employee_login():
    if employee_required(): return redirect('/employee/portal')
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '').strip()
        if not email or not password:
            return render_template("employee_login.html", error=True)
        cur = mysql.connection.cursor()
        cur.execute("SELECT id, name, email, password, department, company_id FROM employees WHERE email=%s AND password=%s", (email, password))
        emp = cur.fetchone()
        cur.close()
        if emp:
            session['employee_id'] = emp[0]
            session['employee_name'] = emp[1]
            return redirect('/employee/portal')
        return render_template("employee_login.html", error=True)
    return render_template("employee_login.html")

@app.route('/employee/portal')
def employee_portal():
    if not employee_required(): return redirect('/employee/login')
    emp_id = session['employee_id']
    emp_name = session['employee_name']
    cur = mysql.connection.cursor()
    cur.execute("SELECT id, name, email, department, company_id FROM employees WHERE id=%s", (emp_id,))
    emp = cur.fetchone()
    today = datetime.date.today()
    today_str = today.strftime('%Y-%m-%d')
    month_start = today.replace(day=1)
    week_start = today - timedelta(days=today.weekday())

    cur.execute("SELECT id, checkin, checkout FROM attendance WHERE name=%s AND date=%s", (emp_name, today))
    today_att = cur.fetchone()
    already_checkedin = today_att is not None
    already_checkedout = today_att is not None and today_att[2] is not None

    cur.execute("SELECT id, name, date, week, checkin, checkout FROM attendance WHERE name=%s ORDER BY date DESC", (emp_name,))
    att_rows = cur.fetchall()
    attendance_records = [(r[0],r[1],to_str(r[2]),r[3],str(r[4]) if r[4] else None,str(r[5]) if r[5] else None) for r in att_rows]

    cur.execute("SELECT COUNT(*) FROM attendance WHERE name=%s AND date>=%s AND date<=%s", (emp_name, month_start, today))
    month_days = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM attendance WHERE name=%s AND date>=%s AND date<=%s", (emp_name, week_start, today))
    week_days = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM attendance WHERE name=%s", (emp_name,))
    total_att = cur.fetchone()[0]
    try:
        cur.execute("SELECT TIME_FORMAT(AVG(TIME_TO_SEC(checkin)), '%%H:%%i') FROM attendance WHERE name=%s AND date>=%s", (emp_name, month_start))
        avg_checkin = cur.fetchone()[0]
    except Exception:
        avg_checkin = None

    attendance_stats = {'month_days': month_days, 'week_days': week_days, 'total': total_att, 'avg_checkin': avg_checkin or '—'}

    present_dates = {r[2] for r in attendance_records if r[2]}
    year, month_num = today.year, today.month
    num_days = calendar.monthrange(year, month_num)[1]
    dow_labels = ['Mo','Tu','We','Th','Fr','Sa','Su']
    calendar_days = []
    for d in range(1, num_days+1):
        date_obj = datetime.date(year, month_num, d)
        date_str = date_obj.strftime('%Y-%m-%d')
        if date_str > today_str: status = 'future'
        elif date_str == today_str: status = 'today'
        elif date_str in present_dates: status = 'present'
        else: status = 'absent'
        calendar_days.append({'day': d, 'date': date_str, 'status': status, 'dow': dow_labels[date_obj.weekday()]})

    cur.execute("""
        SELECT id, title, description, assigned_to, assigned_by, priority, status,
               due_date, created_at, proof_text, proof_link, proof_image,
               proof_submitted_at, admin_verdict, admin_note
        FROM tasks WHERE assigned_to=%s
        ORDER BY FIELD(status,'proof_submitted','in_progress','accepted','pending','completed','rejected'),
                 FIELD(priority,'high','medium','low')
    """, (emp_id,))
    raw_tasks = cur.fetchall()
    tasks = [(t[0],t[1],t[2],t[3],t[4],t[5],t[6],to_str(t[7]),to_str(t[8]),t[9],t[10],t[11],to_str(t[12]),t[13],t[14]) for t in raw_tasks]

    pending_tasks = sum(1 for t in tasks if t[6] in ('pending','accepted'))
    task_stats = {
        'total': len(tasks),
        'pending': sum(1 for t in tasks if t[6]=='pending'),
        'in_progress': sum(1 for t in tasks if t[6] in ('accepted','in_progress')),
        'completed': sum(1 for t in tasks if t[6]=='completed'),
        'proof_submitted': sum(1 for t in tasks if t[6]=='proof_submitted'),
    }

    cur.execute("SELECT id, employee_id, log_date, work_done, hours_worked FROM work_logs WHERE employee_id=%s ORDER BY log_date DESC", (emp_id,))
    work_logs = [(lg[0],lg[1],to_str(lg[2]),lg[3],lg[4]) for lg in cur.fetchall()]
    cur.close()

    employee_data = {'name': emp[1], 'email': emp[2], 'department': emp[3] or 'General', 'company_id': emp[4] or '—'}
    return render_template("employee_portal.html",
        employee=employee_data, attendance_records=attendance_records,
        attendance_stats=attendance_stats, calendar_days=calendar_days,
        current_month=today.strftime('%B %Y'), tasks=tasks,
        task_stats=task_stats, pending_tasks=pending_tasks,
        work_logs=work_logs, today=today_str,
        already_checkedin=already_checkedin, already_checkedout=already_checkedout
    )

@app.route('/employee/checkin', methods=['POST'])
def employee_checkin():
    if not employee_required(): return jsonify({'error': 'unauthorized'}), 401
    inserted = do_checkin(session['employee_name'])
    if inserted: return jsonify({'status': 'ok', 'message': '✅ Checked in successfully!'})
    return jsonify({'status': 'already', 'message': 'ℹ️ Already checked in today.'})

@app.route('/employee/checkout', methods=['POST'])
def employee_checkout():
    if not employee_required(): return jsonify({'error': 'unauthorized'}), 401
    do_checkout(session['employee_name'])
    return jsonify({'status': 'ok', 'message': '✅ Checked out successfully!'})

@app.route('/employee/task/accept', methods=['POST'])
def employee_task_accept():
    if not employee_required(): return jsonify({'error': 'unauthorized'}), 401
    data = request.get_json()
    task_id = data.get('task_id')
    cur = mysql.connection.cursor()
    cur.execute("UPDATE tasks SET status='accepted', admin_note=NULL WHERE id=%s AND assigned_to=%s AND status='pending'",
                (task_id, session['employee_id']))
    mysql.connection.commit()
    cur.close()
    return jsonify({'status': 'ok'})

@app.route('/employee/task/decline', methods=['POST'])
def employee_task_decline():
    if not employee_required(): return jsonify({'error': 'unauthorized'}), 401
    data = request.get_json()
    task_id = data.get('task_id')
    reason = data.get('reason', '').strip()
    if not reason:
        return jsonify({'status': 'error', 'message': 'Please provide a reason for declining'})
    cur = mysql.connection.cursor()
    cur.execute("""UPDATE tasks SET status='declined', admin_note=%s
                   WHERE id=%s AND assigned_to=%s AND status='pending'""",
                (reason, task_id, session['employee_id']))
    mysql.connection.commit()
    cur.close()
    update_performance(session['employee_id'], 'task_declined', f'Declined task #{task_id}: {reason[:60]}')
    return jsonify({'status': 'ok'})


@app.route('/employee/task/update', methods=['POST'])
def employee_task_update():
    if not employee_required(): return jsonify({'error': 'unauthorized'}), 401
    data = request.get_json()
    task_id = data.get('task_id')
    status = data.get('status')
    if status not in ('accepted', 'in_progress'): return jsonify({'status': 'error'})
    cur = mysql.connection.cursor()
    cur.execute("UPDATE tasks SET status=%s WHERE id=%s AND assigned_to=%s", (status, task_id, session['employee_id']))
    mysql.connection.commit()
    cur.close()
    return jsonify({'status': 'ok'})

@app.route('/employee/task/submit_proof', methods=['POST'])
def employee_task_submit_proof():
    if not employee_required(): return jsonify({'error': 'unauthorized'}), 401
    task_id = request.form.get('task_id')
    proof_text = request.form.get('proof_text', '').strip()
    proof_link = request.form.get('proof_link', '').strip()
    proof_image_path = None
    if 'proof_image' in request.files:
        file = request.files['proof_image']
        if file and file.filename and allowed_file(file.filename):
            import uuid
            ext = file.filename.rsplit('.', 1)[1].lower()
            filename = f"proof_{task_id}_{uuid.uuid4().hex[:8]}.{ext}"
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            proof_image_path = f"proof_uploads/{filename}"
    if not proof_text and not proof_link and not proof_image_path:
        return jsonify({'status': 'error', 'message': 'Please provide at least one proof'})
    cur = mysql.connection.cursor()
    cur.execute("""UPDATE tasks SET proof_text=%s, proof_link=%s, proof_image=%s,
                   proof_submitted_at=%s, status='proof_submitted', admin_verdict='pending'
                   WHERE id=%s AND assigned_to=%s""",
                (proof_text or None, proof_link or None, proof_image_path,
                 datetime.datetime.now(), task_id, session['employee_id']))
    mysql.connection.commit()
    cur.close()
    return jsonify({'status': 'ok', 'message': '✅ Proof submitted!'})

@app.route('/employee/worklog/add', methods=['POST'])
def employee_worklog_add():
    if not employee_required(): return jsonify({'error': 'unauthorized'}), 401
    data = request.get_json()
    log_date = data.get('date')
    hours = data.get('hours')
    work = data.get('work', '').strip()
    if not log_date or not hours or not work:
        return jsonify({'status': 'error', 'message': 'All fields required'})
    cur = mysql.connection.cursor()
    cur.execute("INSERT INTO work_logs(employee_id, log_date, work_done, hours_worked) VALUES(%s,%s,%s,%s)",
                (session['employee_id'], log_date, work, hours))
    mysql.connection.commit()
    cur.close()
    return jsonify({'status': 'ok'})

@app.route('/employee/logout')
def employee_logout():
    session.pop('employee_id', None)
    session.pop('employee_name', None)
    return redirect('/employee/login')




# ════════════════════════════════════════════════════════════════
#  PERFORMANCE ENGINE
# ════════════════════════════════════════════════════════════════

SCORE_RULES = {
    'task_accepted':       0,
    'task_declined':      -10,
    'task_completed':      0,
    'proof_approved':     +20,
    'proof_rejected':     -15,
    'attendance_present':  +2,
    'attendance_late':     -3,
    'attendance_absent':   -5,
}

def get_score_grade(score):
    if score >= 90: return 'A', '#00E87A'
    if score >= 75: return 'B', '#00D4FF'
    if score >= 60: return 'C', '#FBB040'
    if score >= 40: return 'D', '#FF9500'
    return 'F', '#FF5A72'

def ensure_performance_row(cur, emp_id, emp_name, dept):
    cur.execute("SELECT id FROM performance_scores WHERE employee_id=%s", (emp_id,))
    if not cur.fetchone():
        cur.execute(
            "INSERT INTO performance_scores(employee_id, employee_name, department) VALUES(%s,%s,%s)",
            (emp_id, emp_name, dept or 'General')
        )

def update_performance(emp_id, action, reason=""):
    points = SCORE_RULES.get(action, 0)
    try:
        cur = mysql.connection.cursor()
        cur.execute("SELECT name, department FROM employees WHERE id=%s", (emp_id,))
        row = cur.fetchone()
        if not row:
            cur.close(); return
        emp_name, dept = row
        ensure_performance_row(cur, emp_id, emp_name, dept)
        counter_map = {
            'task_accepted':      ('tasks_accepted',  1),
            'task_declined':      ('tasks_declined',  1),
            'task_completed':     ('tasks_completed', 1),
            'proof_approved':     ('proofs_approved', 1),
            'proof_rejected':     ('proofs_rejected', 1),
            'attendance_present': ('days_present',    1),
            'attendance_late':    ('days_late',       1),
            'attendance_absent':  ('days_absent',     1),
        }
        if action in counter_map:
            col, val = counter_map[action]
            cur.execute(f"UPDATE performance_scores SET {col}={col}+%s WHERE employee_id=%s", (val, emp_id))
        if points != 0:
            cur.execute("""
                UPDATE performance_scores
                SET score = GREATEST(0, LEAST(100, score + %s)), last_updated = NOW()
                WHERE employee_id = %s
            """, (points, emp_id))
            cur.execute(
                "INSERT INTO performance_log(employee_id, action, points, reason) VALUES(%s,%s,%s,%s)",
                (emp_id, action, points, reason)
            )
        mysql.connection.commit()
        cur.close()
    except Exception as e:
        print(f"Performance update error: {e}")


# ════════════════════════════════════════════════════════════════
#  CHART DATA API ROUTES
# ════════════════════════════════════════════════════════════════

@app.route('/api/employee/id_by_name')
def employee_id_by_name():
    if 'superadmin' not in session and 'admin' not in session:
        return jsonify({'error': 'unauthorized'}), 401
    name = request.args.get('name', '')
    cur = mysql.connection.cursor()
    cur.execute("SELECT id FROM employees WHERE name=%s LIMIT 1", (name,))
    row = cur.fetchone()
    cur.close()
    return jsonify({'id': row[0] if row else None})

@app.route('/api/charts/employee/<int:emp_id>')
def charts_employee(emp_id):
    # Allow superadmin and admin to view any employee's charts
    if 'employee_id' not in session and 'superadmin' not in session and 'admin' not in session:
        return jsonify({'error': 'unauthorized'}), 401
    cur = mysql.connection.cursor()
    # Determine employee name from session or from DB by ID
    if 'employee_id' in session and session.get('employee_id') == emp_id:
        emp_name = session.get('employee_name', '')
    else:
        cur.execute("SELECT name FROM employees WHERE id=%s LIMIT 1", (emp_id,))
        row = cur.fetchone()
        emp_name = row[0] if row else ''

    cur.execute("""
        SELECT date, checkin, checkout
        FROM attendance WHERE name=%s ORDER BY date DESC LIMIT 30
    """, (emp_name,))
    att_rows = cur.fetchall()
    att_dates = [str(r[0]) for r in reversed(att_rows)]
    # Derive hours from checkin/checkout if available, else 0
    def calc_hours(cin, cout):
        try:
            if cin and cout:
                from datetime import datetime as dt
                fmt = '%H:%M:%S'
                diff = dt.strptime(str(cout), fmt) - dt.strptime(str(cin), fmt)
                return round(diff.seconds / 3600, 2)
        except:
            pass
        return 0
    att_hours = [calc_hours(r[1], r[2]) for r in reversed(att_rows)]
    # Determine late: checkin after 09:15
    def is_late(cin):
        try:
            if cin:
                h, m = int(str(cin).split(':')[0]), int(str(cin).split(':')[1])
                return 1 if (h > 9 or (h == 9 and m > 15)) else 0
        except:
            pass
        return 0
    att_late = [is_late(r[1]) for r in reversed(att_rows)]

    cur.execute(
        "SELECT DATE_FORMAT(date, '%%Y-%%m') as month, COUNT(*) as days "
        "FROM attendance WHERE name=%s "
        "GROUP BY month ORDER BY month DESC LIMIT 6",
        (emp_name,))
    monthly = cur.fetchall()
    monthly_labels = [r[0] for r in reversed(monthly)]
    monthly_days   = [r[1] for r in reversed(monthly)]

    cur.execute("""
        SELECT score, tasks_accepted, tasks_declined, tasks_completed,
               proofs_rejected, days_present, days_late, days_absent
        FROM performance_scores WHERE employee_id=%s
    """, (emp_id,))
    perf = cur.fetchone()

    cur.execute("""
        SELECT action, points, reason, created_at
        FROM performance_log WHERE employee_id=%s
        ORDER BY created_at DESC LIMIT 10
    """, (emp_id,))
    logs = [{'action': r[0], 'points': r[1], 'reason': r[2], 'date': str(r[3])} for r in cur.fetchall()]

    cur.execute("SELECT status, COUNT(*) FROM tasks WHERE assigned_to=%s GROUP BY status", (emp_id,))
    task_rows = cur.fetchall()
    cur.close()

    score = round(float(perf[0]), 1) if perf else 100.0
    grade, grade_color = get_score_grade(score)

    return jsonify({
        'attendance': {
            'dates': att_dates, 'hours': att_hours, 'late': att_late,
            'monthly_labels': monthly_labels, 'monthly_days': monthly_days,
        },
        'performance': {
            'score': score, 'grade': grade, 'grade_color': grade_color,
            'tasks_accepted':  perf[1] if perf else 0,
            'tasks_declined':  perf[2] if perf else 0,
            'tasks_completed': perf[3] if perf else 0,
            'proofs_rejected': perf[4] if perf else 0,
            'days_present':    perf[5] if perf else 0,
            'days_late':       perf[6] if perf else 0,
            'days_absent':     perf[7] if perf else 0,
            'log': logs,
        },
        'tasks': {
            'labels': [r[0] for r in task_rows],
            'counts': [r[1] for r in task_rows],
        }
    })


@app.route('/api/charts/admin')
def charts_admin():
    if 'admin' not in session:
        return jsonify({'error': 'unauthorized'}), 401
    dept  = session.get('admin_department', None)
    cur   = mysql.connection.cursor()
    today = datetime.date.today()

    if dept:
        cur.execute("""
            SELECT employee_name, score, days_present, days_late
            FROM performance_scores WHERE department=%s ORDER BY score DESC
        """, (dept,))
    else:
        cur.execute("SELECT employee_name, score, days_present, days_late FROM performance_scores ORDER BY score DESC")
    perf_rows  = cur.fetchall()

    if dept:
        cur.execute(
            "SELECT DATE_FORMAT(a.date, '%%Y-%%m') as m, COUNT(*) FROM attendance a "
            "JOIN employees e ON e.name=a.name WHERE e.department=%s "
            "GROUP BY m ORDER BY m DESC LIMIT 6",
            (dept,))
    else:
        cur.execute("SELECT DATE_FORMAT(date, '%%Y-%%m') as m, COUNT(*) FROM attendance GROUP BY m ORDER BY m DESC LIMIT 6")
    trend = cur.fetchall()

    if dept:
        cur.execute("""
            SELECT t.status, COUNT(*) FROM tasks t JOIN employees e ON t.assigned_to=e.id
            WHERE e.department=%s GROUP BY t.status
        """, (dept,))
    else:
        cur.execute("SELECT status, COUNT(*) FROM tasks GROUP BY status")
    task_rows = cur.fetchall()

    cur.close()
    return jsonify({
        'employees': {
            'names':   [r[0] for r in perf_rows],
            'scores':  [round(float(r[1]),1) for r in perf_rows],
            'present': [r[2] for r in perf_rows],
            'late':    [r[3] for r in perf_rows],
        },
        'trend': {
            'labels': [r[0] for r in reversed(trend)],
            'counts': [r[1] for r in reversed(trend)],
        },
        'tasks': {
            'labels': [r[0] for r in task_rows],
            'counts': [r[1] for r in task_rows],
        },
        'today_count': 0,
        'dept_attendance': {'labels': [], 'rates': []}
    })


@app.route('/api/charts/superadmin')
def charts_superadmin():
    if 'superadmin' not in session:
        return jsonify({'error': 'unauthorized'}), 401
    cur   = mysql.connection.cursor()
    today = datetime.date.today()

    cur.execute("SELECT employee_name, department, score, days_present, days_late, tasks_completed, tasks_declined, proofs_rejected FROM performance_scores ORDER BY score DESC")
    all_perf = cur.fetchall()

    cur.execute("SELECT department, ROUND(AVG(score),1), COUNT(*) FROM performance_scores GROUP BY department ORDER BY 2 DESC")
    dept_perf = cur.fetchall()

    cur.execute("SELECT DATE_FORMAT(date, '%%Y-%%m') as m, COUNT(*) FROM attendance GROUP BY m ORDER BY m DESC LIMIT 12")
    trend = cur.fetchall()

    cur.execute("""
        SELECT e.department, COUNT(DISTINCT e.id), COUNT(DISTINCT a.name)
        FROM employees e LEFT JOIN attendance a ON a.name=e.name AND a.date=%s
        GROUP BY e.department ORDER BY e.department
    """, (today,))
    dept_att = cur.fetchall()

    cur.execute("SELECT status, COUNT(*) FROM tasks GROUP BY status")
    task_status = cur.fetchall()

    cur.execute("SELECT employee_name, department, score FROM performance_scores ORDER BY score DESC LIMIT 5")
    top5 = cur.fetchall()
    cur.execute("SELECT employee_name, department, score FROM performance_scores ORDER BY score ASC LIMIT 5")
    bottom5 = cur.fetchall()
    cur.close()

    return jsonify({
        'all_employees': [{'name':r[0],'dept':r[1],'score':round(float(r[2]),1),'present':r[3],'late':r[4],'completed':r[5],'declined':r[6],'rejected':r[7]} for r in all_perf],
        'dept_performance': {'labels':[r[0] for r in dept_perf],'scores':[float(r[1]) for r in dept_perf],'counts':[r[2] for r in dept_perf]},
        'trend': {'labels':[r[0] for r in reversed(trend)],'counts':[r[1] for r in reversed(trend)]},
        'dept_attendance': {'labels':[r[0] for r in dept_att],'total':[r[1] for r in dept_att],'present':[r[2] for r in dept_att]},
        'task_status': {'labels':[r[0] for r in task_status],'counts':[r[1] for r in task_status]},
        'top5':    [{'name':r[0],'dept':r[1],'score':round(float(r[2]),1)} for r in top5],
        'bottom5': [{'name':r[0],'dept':r[1],'score':round(float(r[2]),1)} for r in bottom5],
    })


@app.route('/api/performance/recalculate', methods=['POST'])
def api_recalculate():
    if 'admin' not in session and 'superadmin' not in session:
        return jsonify({'error': 'unauthorized'}), 401
    cur = mysql.connection.cursor()
    cur.execute("SELECT id FROM employees")
    ids = [r[0] for r in cur.fetchall()]
    cur.close()
    for eid in ids:
        update_performance(eid, 'attendance_present', 'recalc')
    return jsonify({'status': 'ok', 'message': f'Recalculated {len(ids)} employees'})


@app.route('/powerbi/export')
def powerbi_export():
    if 'admin' not in session and 'superadmin' not in session:
        return "Unauthorized", 401
    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT a.name, a.date, a.checkin, a.checkout,
               e.department,
               COALESCE(p.score, 100)
        FROM attendance a
        LEFT JOIN employees e ON e.name=a.name
        LEFT JOIN performance_scores p ON p.employee_id=e.id
        ORDER BY a.date DESC
    """)
    data = cur.fetchall()
    cur.close()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Name','Date','Check In','Check Out','Department','Performance Score'])
    writer.writerows(data)
    output.seek(0)
    response = make_response(output.getvalue())
    response.headers['Content-Type'] = 'text/csv'
    response.headers['Content-Disposition'] = 'attachment; filename=powerbi_data.csv'
    return response

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False, threaded=True)
