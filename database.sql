-- TicketPulse PostgreSQL schema (v2)
-- Adds: departments, ticket statuses, staff login credentials, per-status
-- critical flags. Run once against your PostgreSQL database before starting
-- the app — migrate.py applies this and seeds a default manager account.

CREATE TABLE IF NOT EXISTS departments (
  id BIGSERIAL PRIMARY KEY,
  name TEXT NOT NULL UNIQUE,
  active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS ticket_statuses (
  id BIGSERIAL PRIMARY KEY,
  name TEXT NOT NULL UNIQUE,
  active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS managers (
  id BIGSERIAL PRIMARY KEY,
  full_name TEXT NOT NULL,
  username TEXT NOT NULL UNIQUE,
  password_hash TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

DROP TABLE IF EXISTS staff CASCADE;

CREATE TABLE staff (
  id BIGSERIAL PRIMARY KEY,
  full_name TEXT NOT NULL,
  role_title TEXT NOT NULL,
  department_id BIGINT REFERENCES departments(id) ON DELETE SET NULL,
  username TEXT NOT NULL UNIQUE,
  password_hash TEXT NOT NULL,
  active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS daily_reports (
  id BIGSERIAL PRIMARY KEY,
  staff_id BIGINT NOT NULL REFERENCES staff(id) ON DELETE CASCADE,
  report_date DATE NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- One row per status the staff member reported that day. Each row can be
-- marked critical individually (previously this was one flag per whole
-- report — now it's per status line).
DROP TABLE IF EXISTS report_items CASCADE;

CREATE TABLE report_items (
  id BIGSERIAL PRIMARY KEY,
  report_id BIGINT NOT NULL REFERENCES daily_reports(id) ON DELETE CASCADE,
  status_id BIGINT NOT NULL REFERENCES ticket_statuses(id),
  pending_count INTEGER NOT NULL DEFAULT 0 CHECK (pending_count >= 0),
  is_critical BOOLEAN NOT NULL DEFAULT FALSE,
  manager_remark TEXT,
  follow_up_date DATE,
  CONSTRAINT critical_item_details CHECK (
    (is_critical = FALSE) OR (manager_remark IS NOT NULL AND follow_up_date IS NOT NULL)
  )
);

CREATE INDEX IF NOT EXISTS daily_reports_date_idx ON daily_reports(report_date);
CREATE INDEX IF NOT EXISTS daily_reports_staff_idx ON daily_reports(staff_id);
CREATE INDEX IF NOT EXISTS report_items_report_idx ON report_items(report_id);
CREATE INDEX IF NOT EXISTS report_items_status_idx ON report_items(status_id);
CREATE INDEX IF NOT EXISTS staff_department_idx ON staff(department_id);