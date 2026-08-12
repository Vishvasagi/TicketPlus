-- Migration: admin-staff linkage + standalone manager accounts support
-- Run this once against the existing TicketPulse database.

-- Staff members can be flagged as admin staff, granting them a linked
-- login on the Manager page using the same username/password.
ALTER TABLE staff
  ADD COLUMN IF NOT EXISTS is_admin BOOLEAN NOT NULL DEFAULT FALSE;

-- Links a managers row back to the staff row that created it (NULL for
-- standalone manager accounts created directly on the Managers tab).
-- Deleting the staff record removes the linked manager login too.
ALTER TABLE managers
  ADD COLUMN IF NOT EXISTS staff_id BIGINT UNIQUE REFERENCES staff(id) ON DELETE CASCADE;
