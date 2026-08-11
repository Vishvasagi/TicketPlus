"""
TicketPulse — Staff service.

Deployed as its own Render web service, separate from the manager service.
Serves staff.html and exposes only what the staff portal needs:
  - GET  /api/staff     (to populate the "who are you" dropdown)
  - POST /api/reports   (to submit a daily report)

Both this service and manager_app.py connect to the same DATABASE_URL.
"""

import os

from flask import Flask, jsonify, request, send_from_directory
from dotenv import load_dotenv

from common.db import get_conn, put_conn, dict_cursor, serialize_row

load_dotenv()

PORT = int(os.environ.get("PORT", 3000))

app = Flask(__name__, static_folder="public_staff", static_url_path="")


@app.get("/")
def index():
    return send_from_directory(app.static_folder, "staff.html")


@app.get("/staff.html")
def staff_page():
    return send_from_directory(app.static_folder, "staff.html")


@app.get("/api/staff")
def list_staff():
    conn = get_conn()
    try:
        cur = dict_cursor(conn)
        cur.execute(
            "SELECT id, full_name, role_title, active, created_at "
            "FROM staff WHERE active = TRUE ORDER BY full_name"
        )
        rows = [serialize_row(r) for r in cur.fetchall()]
        return jsonify(rows)
    finally:
        put_conn(conn)


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


@app.get("/api/health")
def health():
    return jsonify({"status": "ok", "service": "staff"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT, debug=os.environ.get("FLASK_DEBUG") == "1")
