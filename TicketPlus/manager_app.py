"""
TicketPulse — Manager service.

Manages departments, ticket statuses, and staff (including login
credentials, edit, delete, and password reset). Also serves the dashboard,
updates feed, and consolidated report, all built on top of report_items
where each status line carries its own critical flag.
"""

import os
import secrets

from flask import Flask, jsonify, request, send_from_directory, session
from dotenv import load_dotenv

from common.db import get_conn, put_conn, dict_cursor, serialize_row, attach_items
from common.auth import hash_password, verify_password, generate_temp_password, login_required

load_dotenv()

PORT = int(os.environ.get("PORT", 4000))

app = Flask(__name__, static_folder="public_manager", static_url_path="")
app.secret_key = os.environ.get("SECRET_KEY") or secrets.token_hex(32)
app.config.update(
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.environ.get("FLASK_DEBUG") != "1",
)


# ---------------------------------------------------------------------------
# Static front end
# ---------------------------------------------------------------------------

@app.get("/")
def index():
    return send_from_directory(app.static_folder, "manager.html")


@app.get("/manager.html")
def manager_page():
    return send_from_directory(app.static_folder, "manager.html")


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

@app.post("/api/auth/login")
def login():
    body = request.get_json(silent=True) or {}
    username = (body.get("username") or "").strip()
    password = body.get("password") or ""

    if not username or not password:
        return jsonify({"error": "Username and password are required."}), 400

    conn = get_conn()
    try:
        cur = dict_cursor(conn)
        cur.execute(
            "SELECT id, full_name, password_hash FROM managers WHERE username = %s",
            (username,),
        )
        row = cur.fetchone()
        if not row or not verify_password(row["password_hash"], password):
            return jsonify({"error": "Invalid username or password."}), 401

        session.clear()
        session["manager_id"] = row["id"]
        return jsonify({"id": row["id"], "full_name": row["full_name"]})
    finally:
        put_conn(conn)


@app.post("/api/auth/logout")
def logout():
    session.clear()
    return jsonify({"ok": True})


@app.get("/api/auth/me")
def me():
    manager_id = session.get("manager_id")
    if not manager_id:
        return jsonify({"error": "Not logged in."}), 401

    conn = get_conn()
    try:
        cur = dict_cursor(conn)
        cur.execute("SELECT id, full_name, username FROM managers WHERE id = %s", (manager_id,))
        row = cur.fetchone()
        if not row:
            session.clear()
            return jsonify({"error": "Not logged in."}), 401
        return jsonify(row)
    finally:
        put_conn(conn)


@app.post("/api/auth/change-password")
@login_required("manager_id")
def change_password():
    body = request.get_json(silent=True) or {}
    new_password = body.get("new_password") or ""
    if len(new_password) < 6:
        return jsonify({"error": "New password must be at least 6 characters."}), 400

    conn = get_conn()
    try:
        cur = dict_cursor(conn)
        cur.execute(
            "UPDATE managers SET password_hash = %s WHERE id = %s",
            (hash_password(new_password), session["manager_id"]),
        )
        conn.commit()
        return jsonify({"ok": True})
    finally:
        put_conn(conn)


# ---------------------------------------------------------------------------
# Departments
# ---------------------------------------------------------------------------

@app.get("/api/departments")
@login_required("manager_id")
def list_departments():
    include_inactive = request.args.get("all") == "1"
    conn = get_conn()
    try:
        cur = dict_cursor(conn)
        if include_inactive:
            cur.execute("SELECT id, name, active, created_at FROM departments ORDER BY name")
        else:
            cur.execute(
                "SELECT id, name, active, created_at FROM departments WHERE active = TRUE ORDER BY name"
            )
        return jsonify([serialize_row(r) for r in cur.fetchall()])
    finally:
        put_conn(conn)


@app.post("/api/departments")
@login_required("manager_id")
def create_department():
    body = request.get_json(silent=True) or {}
    name = (body.get("name") or "").strip()
    if not name:
        return jsonify({"error": "name is required."}), 400

    conn = get_conn()
    try:
        cur = dict_cursor(conn)
        try:
            cur.execute(
                "INSERT INTO departments (name) VALUES (%s) "
                "RETURNING id, name, active, created_at",
                (name,),
            )
            conn.commit()
        except Exception as exc:
            conn.rollback()
            if "unique" in str(exc).lower():
                return jsonify({"error": "A department with that name already exists."}), 409
            raise
        return jsonify(serialize_row(cur.fetchone())), 201
    finally:
        put_conn(conn)


@app.patch("/api/departments/<int:dept_id>")
@login_required("manager_id")
def update_department(dept_id):
    body = request.get_json(silent=True) or {}
    fields, params = [], []
    if "name" in body:
        fields.append("name = %s")
        params.append((body.get("name") or "").strip())
    if "active" in body:
        fields.append("active = %s")
        params.append(bool(body["active"]))
    if not fields:
        return jsonify({"error": "Nothing to update."}), 400

    params.append(dept_id)
    conn = get_conn()
    try:
        cur = dict_cursor(conn)
        cur.execute(
            f"UPDATE departments SET {', '.join(fields)} WHERE id = %s "
            f"RETURNING id, name, active, created_at",
            params,
        )
        row = cur.fetchone()
        conn.commit()
        if not row:
            return jsonify({"error": "Department not found."}), 404
        return jsonify(serialize_row(row))
    finally:
        put_conn(conn)


@app.delete("/api/departments/<int:dept_id>")
@login_required("manager_id")
def delete_department(dept_id):
    conn = get_conn()
    try:
        cur = dict_cursor(conn)
        cur.execute("DELETE FROM departments WHERE id = %s RETURNING id", (dept_id,))
        row = cur.fetchone()
        conn.commit()
        if not row:
            return jsonify({"error": "Department not found."}), 404
        return jsonify({"ok": True})
    finally:
        put_conn(conn)


# ---------------------------------------------------------------------------
# Ticket statuses
# ---------------------------------------------------------------------------

@app.get("/api/statuses")
@login_required("manager_id")
def list_statuses():
    include_inactive = request.args.get("all") == "1"
    conn = get_conn()
    try:
        cur = dict_cursor(conn)
        if include_inactive:
            cur.execute("SELECT id, name, active, created_at FROM ticket_statuses ORDER BY name")
        else:
            cur.execute(
                "SELECT id, name, active, created_at FROM ticket_statuses WHERE active = TRUE ORDER BY name"
            )
        return jsonify([serialize_row(r) for r in cur.fetchall()])
    finally:
        put_conn(conn)


@app.post("/api/statuses")
@login_required("manager_id")
def create_status():
    body = request.get_json(silent=True) or {}
    name = (body.get("name") or "").strip()
    if not name:
        return jsonify({"error": "name is required."}), 400

    conn = get_conn()
    try:
        cur = dict_cursor(conn)
        try:
            cur.execute(
                "INSERT INTO ticket_statuses (name) VALUES (%s) "
                "RETURNING id, name, active, created_at",
                (name,),
            )
            conn.commit()
        except Exception as exc:
            conn.rollback()
            if "unique" in str(exc).lower():
                return jsonify({"error": "A status with that name already exists."}), 409
            raise
        return jsonify(serialize_row(cur.fetchone())), 201
    finally:
        put_conn(conn)


@app.patch("/api/statuses/<int:status_id>")
@login_required("manager_id")
def update_status(status_id):
    body = request.get_json(silent=True) or {}
    fields, params = [], []
    if "name" in body:
        fields.append("name = %s")
        params.append((body.get("name") or "").strip())
    if "active" in body:
        fields.append("active = %s")
        params.append(bool(body["active"]))
    if not fields:
        return jsonify({"error": "Nothing to update."}), 400

    params.append(status_id)
    conn = get_conn()
    try:
        cur = dict_cursor(conn)
        cur.execute(
            f"UPDATE ticket_statuses SET {', '.join(fields)} WHERE id = %s "
            f"RETURNING id, name, active, created_at",
            params,
        )
        row = cur.fetchone()
        conn.commit()
        if not row:
            return jsonify({"error": "Status not found."}), 404
        return jsonify(serialize_row(row))
    finally:
        put_conn(conn)


@app.delete("/api/statuses/<int:status_id>")
@login_required("manager_id")
def delete_status(status_id):
    conn = get_conn()
    try:
        cur = dict_cursor(conn)
        cur.execute("DELETE FROM ticket_statuses WHERE id = %s RETURNING id", (status_id,))
        row = cur.fetchone()
        conn.commit()
        if not row:
            return jsonify({"error": "Status not found."}), 404
        return jsonify({"ok": True})
    finally:
        put_conn(conn)


# ---------------------------------------------------------------------------
# Staff administration
# ---------------------------------------------------------------------------

@app.get("/api/staff")
@login_required("manager_id")
def list_staff():
    include_inactive = request.args.get("all") == "1"
    conn = get_conn()
    try:
        cur = dict_cursor(conn)
        where = "" if include_inactive else "WHERE s.active = TRUE"
        cur.execute(
            f"SELECT s.id, s.full_name, s.role_title, s.username, s.active, s.created_at, "
            f"s.department_id, d.name AS department_name "
            f"FROM staff s LEFT JOIN departments d ON d.id = s.department_id "
            f"{where} ORDER BY s.full_name"
        )
        return jsonify([serialize_row(r) for r in cur.fetchall()])
    finally:
        put_conn(conn)


@app.post("/api/staff")
@login_required("manager_id")
def create_staff():
    body = request.get_json(silent=True) or {}
    full_name = (body.get("full_name") or "").strip()
    role_title = (body.get("role_title") or "").strip()
    department_id = body.get("department_id") or None
    username = (body.get("username") or "").strip()
    password = body.get("password") or ""

    if not full_name or not role_title or not username:
        return jsonify({"error": "full_name, role_title, and username are required."}), 400

    generated = False
    if not password:
        password = generate_temp_password()
        generated = True
    elif len(password) < 6:
        return jsonify({"error": "Password must be at least 6 characters."}), 400

    conn = get_conn()
    try:
        cur = dict_cursor(conn)
        try:
            cur.execute(
                "INSERT INTO staff (full_name, role_title, department_id, username, password_hash) "
                "VALUES (%s, %s, %s, %s, %s) "
                "RETURNING id, full_name, role_title, department_id, username, active, created_at",
                (full_name, role_title, department_id, username, hash_password(password)),
            )
            conn.commit()
        except Exception as exc:
            conn.rollback()
            if "unique" in str(exc).lower():
                return jsonify({"error": "That username is already taken."}), 409
            raise

        result = serialize_row(cur.fetchone())
        if generated:
            result["temp_password"] = password
        return jsonify(result), 201
    finally:
        put_conn(conn)


@app.patch("/api/staff/<int:staff_id>")
@login_required("manager_id")
def update_staff(staff_id):
    body = request.get_json(silent=True) or {}
    fields, params = [], []

    if "full_name" in body:
        fields.append("full_name = %s")
        params.append((body.get("full_name") or "").strip())
    if "role_title" in body:
        fields.append("role_title = %s")
        params.append((body.get("role_title") or "").strip())
    if "department_id" in body:
        fields.append("department_id = %s")
        params.append(body.get("department_id") or None)
    if "active" in body:
        fields.append("active = %s")
        params.append(bool(body["active"]))

    if not fields:
        return jsonify({"error": "Nothing to update."}), 400

    params.append(staff_id)
    conn = get_conn()
    try:
        cur = dict_cursor(conn)
        cur.execute(
            f"UPDATE staff SET {', '.join(fields)} WHERE id = %s "
            f"RETURNING id, full_name, role_title, department_id, username, active, created_at",
            params,
        )
        row = cur.fetchone()
        conn.commit()
        if not row:
            return jsonify({"error": "Staff member not found."}), 404
        return jsonify(serialize_row(row))
    finally:
        put_conn(conn)


@app.delete("/api/staff/<int:staff_id>")
@login_required("manager_id")
def delete_staff(staff_id):
    """Hard delete. Their past reports are removed too (ON DELETE CASCADE) —
    deactivating instead of deleting keeps report history if that's wanted."""
    conn = get_conn()
    try:
        cur = dict_cursor(conn)
        cur.execute("DELETE FROM staff WHERE id = %s RETURNING id", (staff_id,))
        row = cur.fetchone()
        conn.commit()
        if not row:
            return jsonify({"error": "Staff member not found."}), 404
        return jsonify({"ok": True})
    finally:
        put_conn(conn)


@app.post("/api/staff/<int:staff_id>/reset-password")
@login_required("manager_id")
def reset_staff_password(staff_id):
    body = request.get_json(silent=True) or {}
    new_password = body.get("new_password") or ""

    generated = False
    if not new_password:
        new_password = generate_temp_password()
        generated = True
    elif len(new_password) < 6:
        return jsonify({"error": "Password must be at least 6 characters."}), 400

    conn = get_conn()
    try:
        cur = dict_cursor(conn)
        cur.execute(
            "UPDATE staff SET password_hash = %s WHERE id = %s RETURNING id",
            (hash_password(new_password), staff_id),
        )
        row = cur.fetchone()
        conn.commit()
        if not row:
            return jsonify({"error": "Staff member not found."}), 404

        result = {"ok": True}
        if generated:
            result["new_password"] = new_password
        return jsonify(result)
    finally:
        put_conn(conn)


# ---------------------------------------------------------------------------
# Dashboard, updates feed, consolidated reports
# ---------------------------------------------------------------------------

REPORT_ITEM_SELECT = (
    "SELECT ri.id, ri.report_id, ri.pending_count, ri.is_critical, "
    "ri.manager_remark, ri.follow_up_date, ts.name AS status_name "
    "FROM report_items ri JOIN ticket_statuses ts ON ts.id = ri.status_id "
)


def _attach_status_items(cur, reports):
    if not reports:
        return reports
    ids = [r["id"] for r in reports]
    cur.execute(REPORT_ITEM_SELECT + "WHERE ri.report_id = ANY(%s) ORDER BY ri.id", (ids,))
    by_report = {}
    for row in cur.fetchall():
        by_report.setdefault(row["report_id"], []).append(serialize_row(row))
    for r in reports:
        r["items"] = by_report.get(r["id"], [])
    return reports


@app.get("/api/dashboard")
@login_required("manager_id")
def dashboard():
    conn = get_conn()
    try:
        cur = dict_cursor(conn)

        cur.execute("SELECT COUNT(*) AS n FROM staff WHERE active = TRUE")
        staff_count = cur.fetchone()["n"]

        cur.execute(
            "SELECT COUNT(*) AS n FROM daily_reports WHERE report_date = CURRENT_DATE"
        )
        update_count = cur.fetchone()["n"]

        cur.execute(
            "SELECT COUNT(*) AS n FROM report_items ri "
            "JOIN daily_reports dr ON dr.id = ri.report_id "
            "WHERE dr.report_date = CURRENT_DATE AND ri.is_critical = TRUE"
        )
        critical_count = cur.fetchone()["n"]

        cur.execute(
            "SELECT ri.id, ri.pending_count, ri.manager_remark, ri.follow_up_date, "
            "ts.name AS status_name, dr.report_date, s.full_name, s.role_title, d.name AS department_name "
            "FROM report_items ri "
            "JOIN ticket_statuses ts ON ts.id = ri.status_id "
            "JOIN daily_reports dr ON dr.id = ri.report_id "
            "JOIN staff s ON s.id = dr.staff_id "
            "LEFT JOIN departments d ON d.id = s.department_id "
            "WHERE ri.is_critical = TRUE "
            "ORDER BY ri.follow_up_date ASC NULLS LAST, dr.created_at DESC "
            "LIMIT 25"
        )
        critical_updates = [serialize_row(r) for r in cur.fetchall()]

        return jsonify(
            {
                "staffCount": staff_count,
                "updateCount": update_count,
                "criticalCount": critical_count,
                "criticalUpdates": critical_updates,
            }
        )
    finally:
        put_conn(conn)


@app.get("/api/updates")
@login_required("manager_id")
def list_updates():
    conn = get_conn()
    try:
        cur = dict_cursor(conn)
        cur.execute(
            "SELECT dr.id, dr.report_date, dr.created_at, s.full_name, s.role_title, "
            "d.name AS department_name "
            "FROM daily_reports dr JOIN staff s ON s.id = dr.staff_id "
            "LEFT JOIN departments d ON d.id = s.department_id "
            "ORDER BY dr.created_at DESC LIMIT 100"
        )
        reports = [serialize_row(r) for r in cur.fetchall()]
        _attach_status_items(cur, reports)
        return jsonify(reports)
    finally:
        put_conn(conn)


@app.get("/api/reports")
@login_required("manager_id")
def consolidated_reports():
    report_date = request.args.get("date")
    staff_id = request.args.get("staff_id")

    clauses = []
    params = []
    if report_date:
        clauses.append("dr.report_date = %s")
        params.append(report_date)
    if staff_id:
        clauses.append("dr.staff_id = %s")
        params.append(staff_id)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""

    conn = get_conn()
    try:
        cur = dict_cursor(conn)
        cur.execute(
            f"SELECT dr.id, dr.report_date, dr.created_at, s.full_name, s.role_title, "
            f"d.name AS department_name "
            f"FROM daily_reports dr JOIN staff s ON s.id = dr.staff_id "
            f"LEFT JOIN departments d ON d.id = s.department_id "
            f"{where} ORDER BY dr.report_date DESC, dr.created_at DESC",
            params,
        )
        reports = [serialize_row(r) for r in cur.fetchall()]
        _attach_status_items(cur, reports)

        total_reports = len(reports)
        total_tickets = sum(item["pending_count"] for r in reports for item in r["items"])
        total_critical = sum(1 for r in reports for item in r["items"] if item["is_critical"])

        return jsonify(
            {
                "reports": reports,
                "totals": {
                    "reports": total_reports,
                    "tickets": total_tickets,
                    "critical": total_critical,
                },
            }
        )
    finally:
        put_conn(conn)


@app.get("/api/health")
def health():
    return jsonify({"status": "ok", "service": "manager"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT, debug=os.environ.get("FLASK_DEBUG") == "1")
