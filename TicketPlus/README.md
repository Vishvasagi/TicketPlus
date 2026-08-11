# TicketPulse — Python (Flask) + PostgreSQL, split into two services

TicketPulse is deployed as **two separate applications** that share one
PostgreSQL database:

- **Staff service** (`staff_app.py`) — its own URL, only serves `staff.html`
  and the routes staff need: viewing the staff list (to pick their name) and
  submitting a daily report.
- **Manager service** (`manager_app.py`) — its own URL, only serves
  `manager.html` and the routes managers need: staff administration, the
  dashboard, the updates feed, and the consolidated report.

Neither service can reach the other's routes — the staff URL has no staff
management endpoints, and the manager URL doesn't accept report submissions
meant for staff. Both talk to the same `DATABASE_URL`, so anything staff
submit shows up for managers immediately, and any staff member a manager
adds is immediately selectable on the staff portal.

## What's in this folder

```
common/
  db.py                Shared Postgres connection pool + helpers (used by both apps)
staff_app.py            Flask app for the staff service
manager_app.py           Flask app for the manager service
migrate.py                Applies database.sql (safe to re-run)
database.sql                PostgreSQL schema (staff, daily_reports, report_items)
requirements.txt           Python dependencies (shared by both services)
.env.example                 Copy to .env and set DATABASE_URL
render.yaml                    Render Blueprint: 1 database + 2 web services
public_staff/
  staff.html                   Staff portal page
  staff.js                       Staff portal logic
  app.css                          Shared stylesheet
public_manager/
  manager.html                  Manager portal page
  manager.js                      Manager portal logic
  app.css                           Shared stylesheet (same file, copied per service)
```

## Local setup

1. Create a PostgreSQL database (e.g. `ticketpulse`) and set `DATABASE_URL`
   in a `.env` file (copy `.env.example`).
2. Install dependencies (shared by both apps):
   ```
   pip install -r requirements.txt
   ```
3. Apply the schema once:
   ```
   python migrate.py
   ```
4. Run each service — pick different ports since they'll run side by side:
   ```
   PORT=3000 python staff_app.py
   PORT=4000 python manager_app.py
   ```
5. Open:
   - `http://localhost:3000/` or `/staff.html` for the staff portal
   - `http://localhost:4000/` or `/manager.html` for the manager portal

## Free Render deployment (two services)

`render.yaml` defines one Render PostgreSQL database plus two web services,
`ticketpulse-staff` and `ticketpulse-manager`, both wired to the same
`DATABASE_URL`.

1. Push this folder to your GitHub repository.
2. In Render, select **New → Blueprint**, connect the repository, and select
   `render.yaml`.
3. Confirm the database and both services (all on the **Free** plan), then
   click **Apply**.
4. Render will give you two separate URLs when the deploy finishes, e.g.:
   - `https://ticketpulse-staff.onrender.com` → staff portal
   - `https://ticketpulse-manager.onrender.com` → manager portal
   Share the staff link with your team and keep the manager link for
   managers only.

The staff service's build command runs `python migrate.py`, applying
`database.sql` to the shared database. Only one service needs to run the
migration — it's harmless if both do, since the schema uses
`IF NOT EXISTS`.

> Important: Render's free PostgreSQL database is a trial/pilot option. It
> expires after 30 days and has no backups. Export the data before expiry or
> upgrade to a paid database for any live business use.

## Deploying manually (not via Blueprint)

If you create the two web services by hand instead of using the Blueprint,
set these explicitly for each — this is the most common source of deploy
failures:

| Setting | Staff service | Manager service |
|---|---|---|
| Build Command | `pip install -r requirements.txt && python migrate.py` | `pip install -r requirements.txt` |
| Start Command | `gunicorn staff_app:app --bind 0.0.0.0:$PORT` | `gunicorn manager_app:app --bind 0.0.0.0:$PORT` |
| `DATABASE_URL` | same Postgres connection string | same Postgres connection string |
| `PYTHON_VERSION` | `3.11.9` (avoids psycopg2-binary wheel issues on newer Python) | `3.11.9` |

## API summary

**Staff service** (`staff_app.py`)
| Method | Path | Purpose |
|---|---|---|
| GET | `/api/staff` | List active staff, for the "who are you" dropdown |
| POST | `/api/reports` | Submit a daily report |

**Manager service** (`manager_app.py`)
| Method | Path | Purpose |
|---|---|---|
| GET | `/api/staff` | List staff (`?all=1` includes inactive) |
| POST | `/api/staff` | Add a staff member |
| PATCH | `/api/staff/<id>` | Activate/deactivate a staff member |
| GET | `/api/dashboard` | Today's metrics + open critical escalations |
| GET | `/api/updates` | Most recent 100 daily reports |
| GET | `/api/reports?date=&staff_id=` | Consolidated, filterable report list + totals |

Do not put database passwords in the HTML or JavaScript files — everything
sensitive stays in `DATABASE_URL` on each service's server side.
