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
backend.migrate_db()  # Run database migrations
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
            
            # Check for leave updates
            summary = backend.get_leave_update_prompt(user["id"])
            if summary:
                flash(f"Your leave balances have been updated:\n{summary}", "info")
                # Update the user's last seen timestamp
                with sqlite3.connect(backend.DB_PATH) as conn:
                    c = conn.cursor()
                    c.execute("UPDATE Users SET upd = ? WHERE id = ?", 
                            (datetime.now().isoformat(), user["id"]))
                    conn.commit()
            
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
    end = request.form.get("end_date","").strip()
    notes = request.form.get("notes","").strip()
    
    # Handle file upload first so we can use the same attachment for all dates
    file = request.files.get("attachment")
    attachment_bytes = None
    filename = None
    
    ALLOWED_EXT = {'.pdf', '.jpg', '.jpeg', '.png', '.gif', '.bmp'}
    if file and file.filename:
        filename = secure_filename(file.filename)
        ext = os.path.splitext(filename)[1].lower()
        if ext not in ALLOWED_EXT:
            flash("File type not allowed. Please upload PDF or image files.", "danger")
            return redirect(url_for("dashboard"))
        attachment_bytes = file.read()
        if not attachment_bytes:
            flash("Empty file uploaded", "danger")
            return redirect(url_for("dashboard"))
    
    try:
        # Convert dates to Python date objects
        start_date = datetime.strptime(start, "%Y-%m-%d").date()
        if end:
            end_date = datetime.strptime(end, "%Y-%m-%d").date()
            if end_date < start_date:
                flash("End date cannot be before start date", "danger")
                return redirect(url_for("dashboard"))
        else:
            end_date = start_date  # Single day leave
            
        # Generate list of dates between start and end
        leave_dates = []
        current_date = start_date
        while current_date <= end_date:
            leave_dates.append(current_date.strftime("%Y-%m-%d"))
            current_date = datetime.fromordinal(current_date.toordinal() + 1).date()
            
        # Submit a separate leave request for each date
        leave_ids = []
        for date in leave_dates:
            lrid = backend.submit_leave(
                u["id"], lt, date, 1, 
                notes + f" (Part of {start} to {end} leave)" if end and end != start else notes,
                None, attachment_bytes, filename
            )
            leave_ids.append(lrid)
            
        if len(leave_ids) > 1:
            flash(f"Leave submitted for {len(leave_ids)} days from {start} to {end}", "success")
        else:
            flash("Leave submitted", "success")
            
    except ValueError:
        flash("Invalid date format", "danger")
        return redirect(url_for("dashboard"))
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
        
        try:
            if is_default:
                if len(date.split("-")) == 3:  # YYYY-MM-DD format
                    date = "-".join(date.split("-")[1:])  # Convert to MM-DD
                backend.add_holiday(date, name)
            else:
                if len(date.split("-")) != 3:
                    flash("Specific holidays must have a year (YYYY-MM-DD format)", "error")
                    return redirect(url_for("admin_holidays"))
                backend.add_holiday(date, name)
                
            flash("Holiday added successfully", "success")
        except Exception as e:
            flash(f"Error adding holiday: {str(e)}", "error")
        return redirect(url_for("admin_holidays"))
    
    # Get holidays for display using the JSON file
    annual_holidays = backend.get_holidays()
    defaults = annual_holidays.get("defaults", {})
    return render_template("admin_holidays.html", 
                         annual_holidays=annual_holidays,
                         defaults=defaults)

@app.route("/admin/holidays/remove", methods=["POST"])
@admin_required
def admin_holidays_remove():
    date = request.form.get("date")
    try:
        backend.remove_holiday(date)
        flash("Holiday removed successfully", "success")
    except Exception as e:
        flash(f"Error removing holiday: {str(e)}", "error")
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
        c.execute("""SELECT attachment_blob, attachment_name, 
                    COALESCE(attachment_image, attachment_blob) as file_content
                    FROM LeaveRequests WHERE id=?""", (leave_id,))
        result = c.fetchone()
        
    if not result or not result[2]:  # Check file_content (either blob or image)
        abort(404)
        
    try:
        file_data = io.BytesIO(result[2])  # Use whichever field has content
        filename = result[1] or f"attachment_{leave_id}"
        
        # Determine mime type based on file extension
        ext = os.path.splitext(filename)[1].lower() if filename else ''
        
        if ext == '.pdf':
            mimetype = 'application/pdf'
            return send_file(
                file_data,
                mimetype=mimetype,
                download_name=None  # Display in browser
            )
        elif ext in ['.png', '.jpg', '.jpeg', '.gif', '.bmp']:
            mimetype = f'image/{ext[1:].replace("jpg", "jpeg")}'
            # Return an HTML page that displays the image
            image_data = base64.b64encode(file_data.read()).decode('utf-8')
            return f"""
            <!DOCTYPE html>
            <html>
            <head>
                <title>Attachment Preview</title>
                <style>
                    body {{ margin: 0; display: flex; justify-content: center; align-items: center; min-height: 100vh; background: #f5f5f5; }}
                    .image-container {{ max-width: 90vw; max-height: 90vh; background: white; padding: 1rem; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
                    img {{ max-width: 100%; max-height: 85vh; object-fit: contain; }}
                    .toolbar {{ display: flex; justify-content: space-between; margin-bottom: 1rem; }}
                    .toolbar a {{ text-decoration: none; color: #0d6efd; padding: 0.5rem 1rem; border: 1px solid #0d6efd; border-radius: 4px; }}
                    .toolbar a:hover {{ background: #0d6efd; color: white; }}
                </style>
            </head>
            <body>
                <div class="image-container">
                    <div class="toolbar">
                        <a href="/attachment/{leave_id}/download" download="{filename}">Download</a>
                        <a href="#" onclick="window.close()">Close</a>
                    </div>
                    <img src="data:{mimetype};base64,{image_data}" alt="Attachment preview">
                </div>
            </body>
            </html>
            """
        else:
            # For unsupported formats, force download
            return send_file(
                file_data,
                mimetype='application/octet-stream',
                download_name=filename
            )
    except Exception as e:
        app.logger.error(f"Error processing attachment: {str(e)}")
        abort(500)

@app.route("/attachment/<int:leave_id>/download")
@login_required
def attachment_download(leave_id):
    with sqlite3.connect(backend.DB_PATH) as conn:
        c = conn.cursor()
        c.execute("""SELECT attachment_blob, attachment_name, 
                    COALESCE(attachment_image, attachment_blob) as file_content
                    FROM LeaveRequests WHERE id=?""", (leave_id,))
        result = c.fetchone()
        
    if not result or not result[2]:  # Check file_content
        abort(404)
        
    try:
        file_data = io.BytesIO(result[2])
        filename = result[1] or f"attachment_{leave_id}"
        
        return send_file(
            file_data,
            mimetype='application/octet-stream',
            download_name=filename
        )
    except Exception as e:
        app.logger.error(f"Error processing attachment download: {str(e)}")
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
