-- TicketPulse PostgreSQL schema
-- Run once against your PostgreSQL database before starting the app.

CREATE TABLE staff (
  id BIGSERIAL PRIMARY KEY,
  full_name TEXT NOT NULL,
  role_title TEXT NOT NULL,
  active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (full_name)
);

CREATE TABLE daily_reports (
  id BIGSERIAL PRIMARY KEY,
  staff_id BIGINT NOT NULL REFERENCES staff(id) ON DELETE RESTRICT,
  report_date DATE NOT NULL,
  is_critical BOOLEAN NOT NULL DEFAULT FALSE,
  manager_remark TEXT,
  follow_up_date DATE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT critical_report_details CHECK (
    (is_critical = FALSE) OR (manager_remark IS NOT NULL AND follow_up_date IS NOT NULL)
  )
);

CREATE TABLE report_items (
  id BIGSERIAL PRIMARY KEY,
  report_id BIGINT NOT NULL REFERENCES daily_reports(id) ON DELETE CASCADE,
  task_name TEXT NOT NULL,
  pending_count INTEGER NOT NULL DEFAULT 0 CHECK (pending_count >= 0)
);

CREATE INDEX daily_reports_date_idx ON daily_reports(report_date);
CREATE INDEX daily_reports_staff_idx ON daily_reports(staff_id);
CREATE INDEX report_items_report_idx ON report_items(report_id);

-- Optional starter staff. Remove or replace these rows before running.
-- INSERT INTO staff (full_name, role_title) VALUES ('Jordan Lee', 'Customer Support');
