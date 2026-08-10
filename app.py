"""
TicketPulse — Python (Flask) + PostgreSQL edition.

Serves the manager/staff HTML front ends from ./public and exposes a small
JSON API under /api/* that the front-end JavaScript talks to.

Run locally:
    pip install -r requirements.txt
    cp .env.example .env      # then set DATABASE_URL
    psql "$DATABASE_URL" -f database.sql
    python app.py
"""

import os
from datetime import date, datetime

from flask import Flask, jsonify, request, send_from_directory
from psycopg2 import pool, extras
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL is not set. Copy .env.example to .env and fill it in, "
        "or set the DATABASE_URL environment variable."
    )

PORT = int(os.environ.get("PORT", 3000))

app = Flask(__name__, static_folder="public", static_url_path="")

# A small connection pool is plenty for this app's traffic profile.
db_pool = pool.SimpleConnectionPool(1, 10, dsn=DATABASE_URL, sslmode=os.environ.get("PGSSLMODE", "prefer"))


def get_conn():
    return db_pool.getconn()


def put_conn(conn):
    db_pool.putconn(conn)


def dict_cursor(conn):
    return conn.cursor(cursor_factory=extras.RealDictCursor)


def to_iso(value):
    """Serialize date/datetime objects for JSON responses."""
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def serialize_row(row):
    return {k: to_iso(v) for k, v in dict(row).items()}


# ---------------------------------------------------------------------------
# Static front end
# ---------------------------------------------------------------------------

@app.get("/")
def index():
    return send_from_directory(app.static_folder, "staff.html")


@app.get("/manager.html")
def manager_page():
    return send_from_directory(app.static_folder, "manager.html")


@app.get("/staff.html")
def staff_page():
    return send_from_directory(app.static_folder, "staff.html")


# ---------------------------------------------------------------------------
# Staff API
# ---------------------------------------------------------------------------

@app.get("/api/staff")
def list_staff():
    """Return staff members. Pass ?all=1 to include inactive staff."""
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
# Daily report submission (staff portal)
# ---------------------------------------------------------------------------

@app.post("/api/reports")
def create_report():
    body = request.get_json(silent=True) or {}

    staff_id = body.get("staff_id")
    report_date = body.get("report_date")
    is_critical = bool(body.get("is_critical"))
    manager_remark = (body.get("manager_remark") or "").strip() or None
    follow_up_date = body.get("follow_up_date") or None
    tasks = body.get("tasks") or []

    if not staff_id or not report_date:
        return jsonify({"error": "staff_id and report_date are required."}), 400

    tasks = [
        {
            "task_name": (t.get("task_name") or "").strip(),
            "pending_count": int(t.get("pending_count") or 0),
        }
        for t in tasks
        if (t.get("task_name") or "").strip()
    ]

    if is_critical and (not manager_remark or not follow_up_date):
        return jsonify(
            {"error": "Critical updates require a manager remark and a follow-up date."}
        ), 400

    conn = get_conn()
    try:
        cur = dict_cursor(conn)
        try:
            cur.execute(
                "INSERT INTO daily_reports "
                "(staff_id, report_date, is_critical, manager_remark, follow_up_date) "
                "VALUES (%s, %s, %s, %s, %s) RETURNING id",
                (staff_id, report_date, is_critical, manager_remark, follow_up_date),
            )
            report_id = cur.fetchone()["id"]

            for task in tasks:
                cur.execute(
                    "INSERT INTO report_items (report_id, task_name, pending_count) "
                    "VALUES (%s, %s, %s)",
                    (report_id, task["task_name"], task["pending_count"]),
                )

            conn.commit()
        except Exception:
            conn.rollback()
            raise

        return jsonify({"id": report_id}), 201
    finally:
        put_conn(conn)


# ---------------------------------------------------------------------------
# Manager: dashboard, updates feed, consolidated reports
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


def _attach_items(cur, reports):
    """Fetch and attach report_items to a list of report dicts, in place."""
    if not reports:
        return reports
    ids = [r["id"] for r in reports]
    cur.execute(
        "SELECT report_id, task_name, pending_count FROM report_items "
        "WHERE report_id = ANY(%s) ORDER BY id",
        (ids,),
    )
    items_by_report = {}
    for row in cur.fetchall():
        items_by_report.setdefault(row["report_id"], []).append(
            {"task_name": row["task_name"], "pending_count": row["pending_count"]}
        )
    for r in reports:
        r["items"] = items_by_report.get(r["id"], [])
    return reports


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
        _attach_items(cur, reports)
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
        _attach_items(cur, reports)

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
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT, debug=os.environ.get("FLASK_DEBUG") == "1")
