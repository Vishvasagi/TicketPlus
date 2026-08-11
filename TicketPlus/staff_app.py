"""
TicketPulse — Staff service.

Staff log in with credentials created by their manager. Once logged in,
they submit a daily report made of one or more "status" lines (drawn from
the manager-defined ticket status list), each with a pending count and its
own optional critical flag + remark + follow-up date.
"""

import os
import secrets

from flask import Flask, jsonify, request, send_from_directory, session
from dotenv import load_dotenv

from common.db import get_conn, put_conn, dict_cursor, serialize_row
from common.auth import verify_password, login_required

load_dotenv()

PORT = int(os.environ.get("PORT", 3000))

app = Flask(__name__, static_folder="public_staff", static_url_path="")
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
    return send_from_directory(app.static_folder, "staff.html")


@app.get("/staff.html")
def staff_page():
    return send_from_directory(app.static_folder, "staff.html")


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
            "SELECT id, full_name, role_title, password_hash, active "
            "FROM staff WHERE username = %s",
            (username,),
        )
        row = cur.fetchone()
        if not row or not row["active"] or not verify_password(row["password_hash"], password):
            return jsonify({"error": "Invalid username or password."}), 401

        session.clear()
        session["staff_id"] = row["id"]
        return jsonify({"id": row["id"], "full_name": row["full_name"], "role_title": row["role_title"]})
    finally:
        put_conn(conn)


@app.post("/api/auth/logout")
def logout():
    session.clear()
    return jsonify({"ok": True})


@app.get("/api/auth/me")
def me():
    staff_id = session.get("staff_id")
    if not staff_id:
        return jsonify({"error": "Not logged in."}), 401

    conn = get_conn()
    try:
        cur = dict_cursor(conn)
        cur.execute(
            "SELECT id, full_name, role_title FROM staff WHERE id = %s AND active = TRUE",
            (staff_id,),
        )
        row = cur.fetchone()
        if not row:
            session.clear()
            return jsonify({"error": "Not logged in."}), 401
        return jsonify(row)
    finally:
        put_conn(conn)


# ---------------------------------------------------------------------------
# Ticket statuses (read-only here — managed by the manager service)
# ---------------------------------------------------------------------------

@app.get("/api/statuses")
@login_required("staff_id")
def list_statuses():
    conn = get_conn()
    try:
        cur = dict_cursor(conn)
        cur.execute(
            "SELECT id, name FROM ticket_statuses WHERE active = TRUE ORDER BY name"
        )
        return jsonify([serialize_row(r) for r in cur.fetchall()])
    finally:
        put_conn(conn)


# ---------------------------------------------------------------------------
# Report submission
# ---------------------------------------------------------------------------

@app.post("/api/reports")
@login_required("staff_id")
def create_report():
    staff_id = session["staff_id"]
    body = request.get_json(silent=True) or {}

    report_date = body.get("report_date")
    items = body.get("items") or []

    if not report_date:
        return jsonify({"error": "report_date is required."}), 400

    cleaned = []
    for item in items:
        status_id = item.get("status_id")
        if not status_id:
            continue
        is_critical = bool(item.get("is_critical"))
        manager_remark = (item.get("manager_remark") or "").strip() or None
        follow_up_date = item.get("follow_up_date") or None

        if is_critical and (not manager_remark or not follow_up_date):
            return jsonify(
                {"error": "Each status marked critical needs a remark and a follow-up date."}
            ), 400

        cleaned.append(
            {
                "status_id": status_id,
                "pending_count": int(item.get("pending_count") or 0),
                "is_critical": is_critical,
                "manager_remark": manager_remark,
                "follow_up_date": follow_up_date,
            }
        )

    if not cleaned:
        return jsonify({"error": "Add at least one status before sending."}), 400

    conn = get_conn()
    try:
        cur = dict_cursor(conn)
        try:
            cur.execute(
                "INSERT INTO daily_reports (staff_id, report_date) VALUES (%s, %s) RETURNING id",
                (staff_id, report_date),
            )
            report_id = cur.fetchone()["id"]

            for item in cleaned:
                cur.execute(
                    "INSERT INTO report_items "
                    "(report_id, status_id, pending_count, is_critical, manager_remark, follow_up_date) "
                    "VALUES (%s, %s, %s, %s, %s, %s)",
                    (
                        report_id,
                        item["status_id"],
                        item["pending_count"],
                        item["is_critical"],
                        item["manager_remark"],
                        item["follow_up_date"],
                    ),
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
