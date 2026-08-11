"""
Applies database.sql against DATABASE_URL, then seeds a default manager
account if the managers table is empty. Safe to run on every deploy.

    python migrate.py
"""

import os
import sys

import psycopg2
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash

load_dotenv()

DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    print("DATABASE_URL is not set.", file=sys.stderr)
    sys.exit(1)

SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "database.sql")

with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
    schema_sql = f.read()

conn = psycopg2.connect(DATABASE_URL)
conn.autocommit = True
try:
    with conn.cursor() as cur:
        cur.execute(schema_sql)
    print("database.sql applied successfully.")

    default_username = os.environ.get("DEFAULT_MANAGER_USERNAME", "admin")
    default_password = os.environ.get("DEFAULT_MANAGER_PASSWORD")

    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM managers")
        (count,) = cur.fetchone()

        if count == 0:
            if not default_password:
                import secrets
                import string

                default_password = "".join(
                    secrets.choice(string.ascii_letters + string.digits) for _ in range(12)
                )

            cur.execute(
                "INSERT INTO managers (full_name, username, password_hash) "
                "VALUES (%s, %s, %s)",
                ("Manager", default_username, generate_password_hash(default_password)),
            )
            print("=" * 60)
            print("No manager account existed — created a default one:")
            print(f"  username: {default_username}")
            print(f"  password: {default_password}")
            print("Log in and change this password, or set DEFAULT_MANAGER_USERNAME")
            print("/ DEFAULT_MANAGER_PASSWORD env vars before the first deploy.")
            print("=" * 60)
        else:
            print(f"{count} manager account(s) already exist — skipping seed.")
finally:
    conn.close()
