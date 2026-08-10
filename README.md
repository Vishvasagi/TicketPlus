# TicketPulse — Python (Flask) + PostgreSQL edition

A staff daily-report tool: staff submit their pending ticket counts (and flag
critical issues for the manager), managers get a dashboard, an updates feed,
and a filterable consolidated report.

This is a Python rewrite of the original Node.js version. The database
schema and the `manager.html` / `staff.html` pages are unchanged; the backend
is now **Flask** instead of Node/Express, and it talks to PostgreSQL with
`psycopg2`.

## What's in this folder

```
app.py            Flask app: serves the front end + JSON API under /api/*
migrate.py         Applies database.sql (safe to re-run — uses IF NOT EXISTS)
database.sql        PostgreSQL schema (staff, daily_reports, report_items)
requirements.txt   Python dependencies
.env.example        Copy to .env and set DATABASE_URL
render.yaml          Blueprint for a free Render deployment
public/
  manager.html        Manager portal
  staff.html            Staff portal
  app.css                Shared stylesheet
  manager.js             Manager portal logic (calls /api/*)
  staff.js                 Staff portal logic (calls /api/*)
```

## Local setup

1. Create a PostgreSQL database named `ticketpulse` (or use a managed
   provider such as Supabase, Neon, AWS RDS, or Render PostgreSQL).
2. Copy `.env.example` to `.env` and set `DATABASE_URL`.
3. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
4. Apply the schema:
   ```
   python migrate.py
   ```
5. Start the app:
   ```
   python app.py
   ```
6. Open `http://localhost:3000/staff.html` or `http://localhost:3000/manager.html`.

For production, run it behind gunicorn instead of the Flask dev server:
```
gunicorn app:app --bind 0.0.0.0:$PORT
```

## Free Render deployment

This repository includes `render.yaml`, which creates both the Python web
service and a Render PostgreSQL database.

1. Push this folder to your GitHub repository.
2. Create or sign in to a [Render account](https://render.com/).
3. In Render, select **New → Blueprint**, connect the GitHub repository, and
   select `render.yaml`.
4. Confirm the service and database, both on the **Free** plan, then click
   **Apply**.
5. When the deployment completes, open the service URL shown by Render:
   - `/manager.html` for managers
   - `/staff.html` for staff

The build command installs dependencies and runs `migrate.py`, which applies
`database.sql` against the Render PostgreSQL database on every deploy.

> Important: Render's free PostgreSQL database is a trial/pilot option. It
> expires after 30 days and has no backups. Export the data before expiry or
> upgrade to a paid database for any live business use.

## API summary

| Method | Path                | Purpose |
|---|---|---|
| GET | `/api/staff` | List active staff (`?all=1` includes inactive) |
| POST | `/api/staff` | Add a staff member `{ full_name, role_title }` |
| PATCH | `/api/staff/<id>` | Set `{ active: true/false }` |
| POST | `/api/reports` | Submit a daily report `{ staff_id, report_date, is_critical, manager_remark, follow_up_date, tasks: [{task_name, pending_count}] }` |
| GET | `/api/dashboard` | Active staff count, today's updates, today's critical count, open critical list |
| GET | `/api/updates` | Most recent 100 daily reports with their task items |
| GET | `/api/reports?date=&staff_id=` | Consolidated, filterable report list + totals |

Do not put database passwords in the HTML or JavaScript files — everything
sensitive stays in `DATABASE_URL` on the server side.
