"""
TicketPulse — Manager service.

Deployed as its own Render web service, separate from the staff service.
Serves manager.html and exposes everything the manager portal needs:
staff administration, dashboard, updates feed, and consolidated reports.

Both this service and staff_app.py connect to the same DATABASE_URL.
"""

import os

from flask import Flask, jsonify, request, send_from_directory
from dotenv import load_dotenv

from common.db import get_conn, put_conn, dict_cursor, serialize_row, attach_items

load_dotenv()

PORT = int(os.environ.get("PORT", 4000))

app = Flask(__name__, static_folder="public_manager", static_url_path="")


@app.get("/")
def index():
    return send_from_directory(app.static_folder, "manager.html")


@app.get("/manager.html")
def manager_page():
    return send_from_directory(app.static_folder, "manager.html")


# ---------------------------------------------------------------------------
# Staff administration
# ---------------------------------------------------------------------------

@app.get("/api/staff")
def list_staff():
    """Pass ?all=1 to include inactive staff (used by the reports filter)."""
    include_inactive = request.args.get("all") == "1"
    conn = get_conn()
    try:
        cur = dict_cursor(conn)
        if include_inactive:
            cur.execute(
                "SELECT id, full_name, role_title, active, created_at "
                "FROM staff ORDER BY full_name"
            )
        else:
            cur.execute(
                "SELECT id, full_name, role_title, active, created_at "
                "FROM staff WHERE active = TRUE ORDER BY full_name"
            )
        rows = [serialize_row(r) for r in cur.fetchall()]
        return jsonify(rows)
    finally:
        put_conn(conn)


@app.post("/api/staff")
def create_staff():
    body = request.get_json(silent=True) or {}
    full_name = (body.get("full_name") or "").strip()
    role_title = (body.get("role_title") or "").strip()

    if not full_name or not role_title:
        return jsonify({"error": "full_name and role_title are required."}), 400

    conn = get_conn()
    try:
        cur = dict_cursor(conn)
        try:
            cur.execute(
                "INSERT INTO staff (full_name, role_title) VALUES (%s, %s) "
                "RETURNING id, full_name, role_title, active, created_at",
                (full_name, role_title),
            )
            conn.commit()
        except Exception as exc:
            conn.rollback()
            if "unique" in str(exc).lower():
                return jsonify({"error": "A staff member with that name already exists."}), 409
            raise
        return jsonify(serialize_row(cur.fetchone())), 201
    finally:
        put_conn(conn)


@app.patch("/api/staff/<int:staff_id>")
def update_staff(staff_id):
    """Toggle a staff member's active flag, e.g. { "active": false }."""
    body = request.get_json(silent=True) or {}
    if "active" not in body:
        return jsonify({"error": "active is required."}), 400

    conn = get_conn()
    try:
        cur = dict_cursor(conn)
        cur.execute(
            "UPDATE staff SET active = %s WHERE id = %s "
            "RETURNING id, full_name, role_title, active, created_at",
            (bool(body["active"]), staff_id),
        )
        row = cur.fetchone()
        conn.commit()
        if not row:
            return jsonify({"error": "Staff member not found."}), 404
        return jsonify(serialize_row(row))
    finally:
        put_conn(conn)


# ---------------------------------------------------------------------------
# Dashboard, updates feed, consolidated reports
# ---------------------------------------------------------------------------

@app.get("/api/dashboard")
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
            "SELECT COUNT(*) AS n FROM daily_reports "
            "WHERE report_date = CURRENT_DATE AND is_critical = TRUE"
        )
        critical_count = cur.fetchone()["n"]

        cur.execute(
            "SELECT dr.id, dr.report_date, dr.manager_remark, dr.follow_up_date, "
            "dr.created_at, s.full_name, s.role_title "
            "FROM daily_reports dr JOIN staff s ON s.id = dr.staff_id "
            "WHERE dr.is_critical = TRUE "
            "ORDER BY dr.follow_up_date ASC NULLS LAST, dr.created_at DESC "
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
def list_updates():
    conn = get_conn()
    try:
        cur = dict_cursor(conn)
        cur.execute(
            "SELECT dr.id, dr.report_date, dr.is_critical, dr.manager_remark, "
            "dr.follow_up_date, dr.created_at, s.full_name, s.role_title "
            "FROM daily_reports dr JOIN staff s ON s.id = dr.staff_id "
            "ORDER BY dr.created_at DESC LIMIT 100"
        )
        reports = [serialize_row(r) for r in cur.fetchall()]
        attach_items(cur, reports)
        return jsonify(reports)
    finally:
        put_conn(conn)


@app.get("/api/reports")
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
            f"SELECT dr.id, dr.report_date, dr.is_critical, dr.manager_remark, "
            f"dr.follow_up_date, dr.created_at, s.full_name, s.role_title "
            f"FROM daily_reports dr JOIN staff s ON s.id = dr.staff_id "
            f"{where} ORDER BY dr.report_date DESC, dr.created_at DESC",
            params,
        )
        reports = [serialize_row(r) for r in cur.fetchall()]
        attach_items(cur, reports)

        total_reports = len(reports)
        total_tickets = sum(item["pending_count"] for r in reports for item in r["items"])
        total_critical = sum(1 for r in reports if r["is_critical"])

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
