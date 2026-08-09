-- Adds RiskAlert.propagated_from_creator_id (backend/app/models.py), added
-- to the SQLModel class in the Weeks 5-6 commit but never actually applied
-- to the live table -- create_all() only creates missing tables, it never
-- ALTERs existing ones, so this column silently didn't exist live while the
-- ORM model claimed it did. Every POST /alerts against the real DB was
-- failing with `psycopg2.errors.UndefinedColumn` until this was applied
-- directly on 2026-08-09 (verified via information_schema.columns before
-- and after, and a real insert/delete round-trip) -- this file makes that
-- fix reproducible/auditable instead of a one-off manual ALTER with no
-- record.
--
-- Safe to re-run.

alter table riskalert add column if not exists propagated_from_creator_id uuid;
