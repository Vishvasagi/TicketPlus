"""
Applies database.sql against DATABASE_URL. Safe to run on every deploy —
the schema uses CREATE TABLE/INDEX IF NOT EXISTS.

    python migrate.py
"""

import os
import sys

import psycopg2
from dotenv import load_dotenv

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
finally:
    conn.close()
