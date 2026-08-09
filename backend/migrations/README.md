# Track C-owned migrations

`app/database.py::init_db()` uses `SQLModel.metadata.create_all()` for
`fusionscore`/`riskalert`, which is only safe for **creating tables that
don't exist yet** -- it silently does nothing to a table that already
exists, even if the SQLModel class gained new columns since. That gap bit
us for real on 2026-08-09: `RiskAlert.propagated_from_creator_id` was added
to `models.py` in the Weeks 5-6 commit, but never reached the live Supabase
table, so every `POST /alerts` against the real DB was failing with
`UndefinedColumn` until it was caught and fixed (see `0002_*.sql`).

**Rule going forward:** any change to an *existing* Track C-owned table's
columns (not a brand-new table) needs a numbered `.sql` file here, applied
by hand against the live DB (`engine.begin()` + the SQL, or the Supabase
SQL editor) -- `create_all()` will not do it for you. Numbered like Track
A's `supabase/migrations/`, but kept in this separate folder since Track C
doesn't own their migrations and shouldn't write into their numbering.
