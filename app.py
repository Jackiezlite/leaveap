from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file, jsonify, abort
import backend, os, io, sqlite3
from werkzeug.utils import secure_filename
from datetime import datetime
import base64

def get_leave_details(leave_id: int):
    """Get leave request details including attachment info"""
    if not leave_id:
        return None
    
    with sqlite3.connect(backend.DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("""
            SELECT lr.*, u.username 
            FROM LeaveRequests lr 
            JOIN Users u ON lr.user_id = u.id 
            WHERE lr.id = ?
        """, (leave_id,))
        result = c.fetchone()
        
        if result:
            return dict(result)
        return None

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET", "devsecret")
backend.init_db()
app.jinja_env.globals.update(get_leave_details=get_leave_details)
ALLOWED_EXT = {".png", ".jpg", ".jpeg", ".gif", ".pdf"}

def current_user():
    return session.get("user")

def login_required(f):
    from functools import wraps
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not current_user():
            return redirect(url_for("login", next=request.path))
        return f(*args, **kwargs)
    return wrapper

def admin_required(f):
    from functools import wraps
    @wraps(f)
    def wrapper(*args, **kwargs):
        u = current_user()
        if not u or u.get("role") not in ("admin","superadmin","it"):
            flash("Admin access required", "danger")
            return redirect(url_for("dashboard"))
        return f(*args, **kwargs)
    return wrapper

@app.route("/", methods=["GET","POST"])
def login():
    if request.method == "POST":
        name = request.form.get("username","").strip()
        pw = request.form.get("password","")
        user = backend.verify_login(name, pw)
        if user:
            session["user"] = user
            flash("Logged in", "success")
            return redirect(url_for("dashboard"))
        flash("Invalid credentials", "danger")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect(url_for("login"))

@app.route("/dashboard")
@login_required
def dashboard():
    u = current_user()
    leaves = backend.get_user_leaves(u["id"])
    leave_types = backend.get_leave_types()
    return render_template("dashboard.html", user=u, leaves=leaves, leave_types=leave_types)

@app.route("/submit_leave", methods=["POST"])
@login_required
def submit_leave():
    u = current_user()
    lt = request.form.get("type","").strip()
    start = request.form.get("date","").strip()
    days = float(request.form.get("days","1"))
    notes = request.form.get("notes","").strip()
    file = request.files.get("attachment")
    attachment_bytes = None
    filename = None
    if file and file.filename:
        filename = secure_filename(file.filename)
        ext = os.path.splitext(filename)[1].lower()
        if ext not in ALLOWED_EXT:
            flash("File type not allowed", "danger")
            return redirect(url_for("dashboard"))
        attachment_bytes = file.read()
    lrid = backend.submit_leave(u["id"], lt, start, days, notes, None, attachment_bytes, filename)
    flash("Leave submitted", "success")
    return redirect(url_for("dashboard"))

@app.route("/admin/approvals")
@admin_required
def admin_approvals():
    pending = backend.get_pending_leaves()
    return render_template("admin_approvals.html", pending=pending, user=current_user())

@app.route("/admin/approve/<int:leave_id>", methods=["POST"])
@admin_required
def admin_approve(leave_id):
    u = current_user()
    try:
        backend.approve_leave(leave_id, u["id"])
        flash("Leave approved", "success")
    except Exception as e:
        flash(f"Error approving: {e}", "danger")
    return redirect(url_for("admin_approvals"))

@app.route("/admin/reject/<int:leave_id>", methods=["POST"])
@admin_required
def admin_reject(leave_id):
    u = current_user()
    reason = request.form.get("reason","").strip()
    try:
        backend.reject_leave(leave_id, u["id"], reason)
        flash("Leave rejected", "warning")
    except Exception as e:
        flash(f"Error rejecting: {e}", "danger")
    return redirect(url_for("admin_approvals"))

@app.route("/admin/users", methods=["GET","POST"])
@admin_required
def admin_users():
    if request.method == "POST":
        username = request.form.get("username")
        login_name = request.form.get("login_name")
        password = request.form.get("password")
        role = request.form.get("role","user")
        backend.create_user(username, login_name, password, role)
        flash("User created", "success")
        return redirect(url_for("admin_users"))
    with sqlite3.connect(backend.DB_PATH) as conn:
        c = conn.cursor()
        c.execute("SELECT id, username, login_name, role FROM Users ORDER BY username")
        users = c.fetchall()
    return render_template("admin_users.html", users=users, user=current_user())

@app.route("/admin/holidays", methods=["GET", "POST"])
@admin_required
def admin_holidays():
    if request.method == "POST":
        date = request.form.get("date")
        name = request.form.get("name")
        is_default = request.form.get("is_default") == "on"
        
        with sqlite3.connect(backend.DB_PATH) as conn:
            c = conn.cursor()
            c.execute("INSERT INTO Holidays (date, name) VALUES (?, ?)", (date, name))
            if is_default:
                c.execute("INSERT INTO DefaultHolidays (date) VALUES (?)", (date,))
            conn.commit()
            
        return redirect(url_for("admin_holidays"))
        
    return render_template("admin_holidays.html", 
                         annual_holidays=backend.get_holidays(),
                         defaults=backend.get_default_holidays())

@app.route("/admin/holidays/remove", methods=["POST"])
@admin_required
def admin_holidays_remove():
    date = request.form.get("date")
    backend.remove_holiday(date)
    flash("Holiday removed", "success")
    return redirect(url_for("admin_holidays"))

@app.route("/calendar")
@login_required
def calendar_view():
    with sqlite3.connect(backend.DB_PATH) as conn:
        c = conn.cursor()
        c.execute("SELECT username FROM Users ORDER BY username")
        users = [r[0] for r in c.fetchall()]
    return render_template("calendar.html", users=users, user=current_user())

@app.route("/calendar/events")
@login_required
def calendar_events():
    user = request.args.get("user")
    year = request.args.get("year")
    events = backend.get_calendar_events(username=user if user else None, year=int(year) if year else None)
    return jsonify(events)

@app.route("/admin/audit")
@admin_required
def admin_audit():
    logs = backend.get_audit_logs()
    return render_template("admin_audit.html", logs=logs, user=current_user())

@app.route("/attachment/<int:leave_id>")
@login_required
def attachment_preview(leave_id):
    with sqlite3.connect(backend.DB_PATH) as conn:
        c = conn.cursor()
        c.execute("SELECT attachment_image FROM LeaveRequests WHERE id=?", (leave_id,))
        result = c.fetchone()
        
    if not result or not result[0]:
        abort(404)
        
    try:
        file_data = io.BytesIO(result[0])
        return send_file(
            file_data,
            mimetype='application/octet-stream',
            download_name=f"attachment_{leave_id}"
        )
    except Exception as e:
        app.logger.error(f"Error processing attachment: {str(e)}")
        abort(500)

@app.route("/reports/monthly", methods=["GET","POST"])
@admin_required
def reports_monthly():
    if request.method == "POST":
        year = int(request.form.get("year"))
        month = int(request.form.get("month"))
        with sqlite3.connect(backend.DB_PATH) as conn:
            c = conn.cursor()
            c.execute("""SELECT lr.id, u.username, lr.leave_type, lr.start_date, lr.num_days FROM LeaveRequests lr JOIN Users u ON lr.user_id=u.id WHERE strftime('%Y', lr.start_date)=? AND strftime('%m', lr.start_date)=? AND lr.status='Approved'""", (str(year), f"{month:02d}"))
            rows = c.fetchall()
        return render_template("reports_result.html", rows=rows, year=year, month=month, user=current_user())
    return render_template("reports.html", user=current_user())

@app.route("/admin/audit/edit", methods=["POST"])
@admin_required
def admin_audit_edit():
    try:
        log_id = request.form.get('id')
        field = request.form.get('field')
        value = request.form.get('value')
        
        with sqlite3.connect(backend.DB_PATH) as conn:
            c = conn.cursor()
            # Use parameterized query safely
            query = f"UPDATE LeaveAudit SET {field}=? WHERE id=?"
            c.execute(query, (value, log_id))
            conn.commit()
            
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/admin/holidays/edit", methods=["POST"])
@admin_required
def edit_holiday():
    try:
        date = request.form.get('date')
        name = request.form.get('name')
        
        with sqlite3.connect(backend.DB_PATH) as conn:
            c = conn.cursor()
            c.execute("UPDATE Holidays SET name = ? WHERE date = ?", (name, date))
            conn.commit()
        
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/admin/holidays/delete", methods=["POST"])
@admin_required
def delete_holiday():
    try:
        date = request.form.get('date')
        
        with sqlite3.connect(backend.DB_PATH) as conn:
            c = conn.cursor()
            c.execute("DELETE FROM Holidays WHERE date = ?", (date,))
            conn.commit()
            
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/admin/holidays/make-default", methods=["POST"])
@admin_required
def make_holiday_default():
    try:
        date = request.form.get('date')
        
        with sqlite3.connect(backend.DB_PATH) as conn:
            c = conn.cursor()
            c.execute("INSERT INTO DefaultHolidays (date) VALUES (?)", (date,))
            conn.commit()
            
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True)
