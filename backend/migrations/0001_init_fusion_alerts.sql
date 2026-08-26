-- Track C-owned tables: fusionscore, riskalert.
-- Retroactive documentation: these were originally created by
-- SQLModel.metadata.create_all() (app/database.py::init_db()) during Weeks
-- 3-4, not a hand-written migration -- that's how the propagated_from_creator_id
-- gap in 0002 happened (create_all() creates missing tables but never
-- ALTERs existing ones, so a later model change silently didn't reach the
-- live table). This file documents the schema as it actually exists live,
-- confirmed via information_schema.columns on 2026-08-09, so future changes
-- have a real paper trail instead of relying on create_all() again.
--
-- Safe to re-run (IF NOT EXISTS everywhere), matching Track A's convention.

create table if not exists fusionscore (
  id                      serial primary key,
  creator_id              uuid not null,
  spillover_score         double precision not null,
  sentiment_risk_score    double precision not null,
  creator_feature_score   double precision not null,
  final_score             double precision not null,
  confidence_low          double precision not null,
  confidence_high         double precision not null,
  risk_adjustment         double precision not null,
  computed_at             timestamp not null
);

create table if not exists riskalert (
  id          serial primary key,
  creator_id  uuid not null,
  severity    varchar not null,
  reason      varchar not null,
  source      varchar not null,
  created_at  timestamp not null,
  resolved    boolean not null
);
