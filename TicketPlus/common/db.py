"""
Shared PostgreSQL connection pool and helpers used by both manager_app.py
and staff_app.py. Both services connect to the same DATABASE_URL — they
just expose different routes on top of the same data.
"""

import os
from datetime import date, datetime

from psycopg2 import pool as pg_pool, extras

_pool = None


def init_pool():
    global _pool
    if _pool is not None:
        return _pool

    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise RuntimeError(
            "DATABASE_URL is not set. Copy .env.example to .env and fill it in, "
            "or set the DATABASE_URL environment variable."
        )

    _pool = pg_pool.SimpleConnectionPool(
        1, 10, dsn=database_url, sslmode=os.environ.get("PGSSLMODE", "prefer")
    )
    return _pool


def get_conn():
    return init_pool().getconn()


def put_conn(conn):
    init_pool().putconn(conn)


def dict_cursor(conn):
    return conn.cursor(cursor_factory=extras.RealDictCursor)


def to_iso(value):
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def serialize_row(row):
    return {k: to_iso(v) for k, v in dict(row).items()}


def attach_items(cur, reports):
    """Fetch and attach report_items to a list of report dicts, in place."""
    if not reports:
        return reports
    ids = [r["id"] for r in reports]
    cur.execute(
        "SELECT ri.id, ri.report_id, ri.pending_count, ri.is_critical, "
        "ri.manager_remark, ri.follow_up_date, ts.name AS status_name "
        "FROM report_items ri LEFT JOIN ticket_statuses ts ON ts.id = ri.status_id "
        "WHERE ri.report_id = ANY(%s) ORDER BY ri.id",
        (ids,),
    )
    items_by_report = {}
    for row in cur.fetchall():
        items_by_report.setdefault(row["report_id"], []).append(
            {
                "id": row["id"],
                "status_name": row["status_name"],
                "pending_count": row["pending_count"],
                "is_critical": row["is_critical"],
                "manager_remark": row["manager_remark"],
                "follow_up_date": to_iso(row["follow_up_date"]),
            }
        )
    for r in reports:
        r["items"] = items_by_report.get(r["id"], [])
    return reports
