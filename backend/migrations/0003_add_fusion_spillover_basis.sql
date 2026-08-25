-- Adds FusionScore.spillover_basis (backend/app/models.py), tracking honest
-- provenance for Track D per P1.6 wiring (c6488a6 checkpoint).
-- Values: trained | inferred | placeholder | isolated
-- Safe to re-run.

alter table fusionscore add column if not exists spillover_basis varchar(12) not null default 'placeholder';
