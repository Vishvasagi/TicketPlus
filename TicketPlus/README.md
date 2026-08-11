# TicketPulse — Python (Flask) + PostgreSQL, two services with login

TicketPulse is deployed as **two separate applications** that share one
PostgreSQL database:

- **Staff service** (`staff_app.py`) — staff log in with credentials their
  manager creates, then submit a daily report made of one or more **status**
  lines (drawn from the manager's ticket status list), each with its own
  pending count and its own optional critical flag.
- **Manager service** (`manager_app.py`) — manager logs in, and can:
  - manage **departments**
  - manage the **ticket status** list staff pick from
  - add / edit / deactivate / **delete** staff, assign them to a department
  - **reset a staff member's password**
  - view the dashboard, updates feed, and a filterable consolidated report

Both services connect to the same `DATABASE_URL`; each has its own login
session and only exposes the routes relevant to that portal.

## What changed from the single-report-line version

- **Departments**: new master list, assignable to staff.
- **Ticket statuses**: new master list, managed by the manager, replacing
  the old freeform "task name" field on the staff form. The staff form is
  now **"Add status"** instead of "Add task."
- **Per-status critical flag**: critical is now marked on each status line
  individually (with its own remark + follow-up date), instead of one
  critical flag for the whole daily report.
- **Login**: both staff and managers now sign in with a username/password
  instead of picking a name from a dropdown / having no auth at all.
- **Manager can edit and delete staff**, not just deactivate them, and can
  **reset a staff member's password**.

> **This is a breaking schema change.** If you have an existing database
> from the earlier version, either point `DATABASE_URL` at a **fresh**
> database, or manually migrate your data — `database.sql` no longer
> matches the old table shapes (`report_items.task_name` is gone, replaced
> by `status_id`; `daily_reports.is_critical` etc. moved to `report_items`).

## What's in this folder

```
common/
  db.py                  Shared Postgres connection pool + helpers
  auth.py                  Password hashing + login-required decorator
staff_app.py               Flask app for the staff service
manager_app.py                Flask app for the manager service
migrate.py                      Applies database.sql + seeds a default manager account
database.sql                       PostgreSQL schema
requirements.txt                  Python dependencies (shared)
.env.example                         Copy to .env and fill in
render.yaml                             Render Blueprint: 1 database + 2 web services
public_staff/
  staff.html, staff.js, app.css
public_manager/
  manager.html, manager.js, app.css
```

## Local setup

1. Create a PostgreSQL database and set `DATABASE_URL` in `.env` (copy
   `.env.example`). Also set `SECRET_KEY` to any random string.
2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
3. Apply the schema and seed the first manager account:
   ```
   python migrate.py
   ```
   This prints a username/password if no manager account exists yet —
   **copy it down, it's only shown once.** Or set
   `DEFAULT_MANAGER_USERNAME` / `DEFAULT_MANAGER_PASSWORD` in `.env` before
   running it to choose your own.
4. Run each service on a different port:
   ```
   PORT=3000 python staff_app.py
   PORT=4000 python manager_app.py
   ```
5. Open `http://localhost:4000/manager.html`, log in, then:
   - Add at least one **ticket status** (Statuses tab)
   - Add a **department** (optional)
   - Add a **staff member** — you'll get their username and an
     auto-generated password (shown once) to give them
6. Open `http://localhost:3000/staff.html` and log in as that staff member
   to submit a report.

## Free Render deployment (two services)

`render.yaml` defines one Render PostgreSQL database plus the two web
services, both wired to the same `DATABASE_URL`, each with an
auto-generated `SECRET_KEY`.

1. Push this folder to your GitHub repository.
2. In Render, **New → Blueprint**, connect the repo, select `render.yaml`.
3. Confirm the database and both services (Free plan), click **Apply**.
4. Once deployed, open the **staff service's build logs** and look for the
   default manager credentials block — copy that password down immediately.
5. Log in to the manager URL, set up statuses/departments/staff, then share
   the staff URL with your team.

> Render's free PostgreSQL database expires after 30 days with no backups.
> Export data or upgrade before then for real use.

## Deploying manually (not via Blueprint)

| Setting | Staff service | Manager service |
|---|---|---|
| Build Command | `pip install -r requirements.txt && python migrate.py` | `pip install -r requirements.txt` |
| Start Command | `gunicorn staff_app:app --bind 0.0.0.0:$PORT` | `gunicorn manager_app:app --bind 0.0.0.0:$PORT` |
| `DATABASE_URL` | same Postgres connection string | same Postgres connection string |
| `SECRET_KEY` | any random string | any random string (can differ per service — sessions aren't shared between them) |
| `PYTHON_VERSION` | `3.11.9` | `3.11.9` |

## API summary

**Staff service** — all routes except `/api/auth/*` require a staff session.
| Method | Path | Purpose |
|---|---|---|
| POST | `/api/auth/login` | `{ username, password }` |
| POST | `/api/auth/logout` | |
| GET | `/api/auth/me` | Current logged-in staff member |
| GET | `/api/statuses` | Active ticket statuses to choose from |
| POST | `/api/reports` | `{ report_date, items: [{status_id, pending_count, is_critical, manager_remark, follow_up_date}] }` |

**Manager service** — all routes except `/api/auth/login` require a manager session.
| Method | Path | Purpose |
|---|---|---|
| POST | `/api/auth/login` / `logout` / `GET /me` | |
| POST | `/api/auth/change-password` | `{ new_password }` for the logged-in manager |
| GET/POST | `/api/departments` | List / create |
| PATCH/DELETE | `/api/departments/<id>` | Rename, activate/deactivate, or delete |
| GET/POST | `/api/statuses` | List / create ticket statuses |
| PATCH/DELETE | `/api/statuses/<id>` | Rename, activate/deactivate, or delete |
| GET/POST | `/api/staff` | List (`?all=1` includes inactive) / create |
| PATCH | `/api/staff/<id>` | Edit name/role/department/active |
| DELETE | `/api/staff/<id>` | Permanently delete (cascades their reports — deactivate instead to keep history) |
| POST | `/api/staff/<id>/reset-password` | `{ new_password? }` — omit to auto-generate |
| GET | `/api/dashboard` | Today's metrics + open critical items |
| GET | `/api/updates` | Most recent 100 reports |
| GET | `/api/reports?date=&staff_id=` | Consolidated, filterable report + totals |

Passwords are hashed with Werkzeug's PBKDF2 implementation before storage —
plaintext passwords are never saved to the database.
