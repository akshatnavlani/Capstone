-- Instagram's native "Paid partnership" label (2026-08-11).
--
-- WHY THIS IS THE PROJECT'S FIRST REAL SCHEMA ADDITION: every other table, FK and
-- brand_id column the model needs already existed — the gaps so far were population,
-- not design. This one is genuinely absent, and it matters because it is a
-- sponsorship signal a caption-only labeler STRUCTURALLY CANNOT SEE.
--
-- Found while extracting collab co-authors: 3 of 97 instagram_posts render a
-- "Paid partnership" label on the page, and that string appears NOWHERE in the
-- caption text. Instagram renders it from the post's branded-content metadata, not
-- from anything the creator typed. So `#ad`-style regex over captions — which is the
-- project's ONLY treatment-label source (PROJECT_PLAN §1: disclosure-tag detection is
-- "the sole source of treatment labels for the entire causal model") — misses it
-- entirely, silently.
--
-- Why it is likely the HIGHEST-PRECISION sponsorship signal available: it is
-- Instagram's own platform-level declaration of a commercial relationship, not a
-- string inferred from creator-authored prose. No false positives from a creator
-- writing "ad" in an unrelated sentence, no misses from a creator using a novel
-- disclosure phrasing.
--
-- OWNERSHIP SPLIT (respects the existing Track A / Track C boundary):
--   Track A (this migration) — writes the RAW OBSERVATION only. Track A observes the
--     label while scraping the page; recording what was seen is a collection concern.
--   Track C — reads it when computing `is_sponsored`. Labeling is theirs and stays
--     theirs; this column deliberately does NOT set is_sponsored itself.
--
-- NULL vs FALSE is meaningful and must not be collapsed:
--   NULL  = not yet observed (row predates this migration, or the page wasn't re-fetched)
--   FALSE = page WAS fetched and carried no paid-partnership label
--   TRUE  = page carried the label
-- Track C should treat NULL as "unknown", not as "not sponsored" — otherwise the 97
-- pre-existing rows would silently read as confirmed-negative when they are simply
-- unmeasured.

alter table instagram_posts
  add column if not exists has_paid_partnership_label boolean;

comment on column instagram_posts.has_paid_partnership_label is
  'Instagram''s native branded-content "Paid partnership" label, observed on the '
  'rendered post page. NOT present in caption text, so caption-only disclosure '
  'detection cannot see it. Track A populates (raw observation); Track C consumes '
  'when computing is_sponsored. NULL = not yet observed (NOT the same as false).';

-- Partial index: the TRUE set is small and is what Track C's labeler will scan for.
create index if not exists idx_instagram_posts_paid_partnership
  on instagram_posts (has_paid_partnership_label)
  where has_paid_partnership_label is true;
