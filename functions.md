# functions.md — Review 1 Codebase — Every Function, Every File

> Generated on `review-1` branch `123f489` (from `main` `816a19e` Review 1 closed 259/54/170). Covers **155 files** assembled from 4 tracks. Each section is `file_path:line` → function signature → purpose / logic / data touched / caller. No code was changed for this doc — it is a read-only inventory.

**How to use:** `grep "def load_predict"` or `grep "SpilloverBadge"` to jump to a function. Tables `supabase/migrations/*` and `backend/migrations/*` are documented as schema, not code. Confidence `basis` everywhere is `trained|inferred|isolated|placeholder` with `hw*100*w1` margins (±13/±21/±10) — see `backend/app/fusion.py:57` and `frontend/src/components/SpilloverBadge.tsx:1`.

**Root docs not repeated here:** `CAPSTONE_NEXT_STEPS.md:1` (single source of truth), `AGENTS.md:1` (worktree + constraints + commands), `CLAUDE.md:1` (think/simplicity/surgical/goal-driven). This file documents the executable code those docs point to.

---

## Table of Contents

- [Track A — Data/Infra](#track-a--datainfra) — `scripts/ingestion/*` + `supabase/migrations/*`
- [Track B — ML-Core](#track-b--ml-core) — `ml/*` + `scripts/*` + `tests/*`
- [Track C — Fusion+Backend](#track-c--fusionbackend) — `backend/app/*`
- [Track D — Frontend+App](#track-d--frontendapp) — `frontend/src/*`

---

## Track A — Data/Infra

### `SCHEMA.md:1` — context
- 12 tables + 1 view live schema; source triples `creators` -> `creator_related_accounts` / `youtube_channels` -> `youtube_videos` -> `youtube_comments` / `instagram_profiles` -> `instagram_posts` -> `instagram_comments` / `reddit_profiles` -> `reddit_posts` -> `reddit_comments` + `brands` + `reddit_post_creators` junction + `creator_sponsorship_events` view.
- `creators.category` CHECK `athlete|team|league|fitness_influencer|lifestyle_influencer|other`; `creator_related_accounts.relation_type` must be literal `"frequent_collaborator"` (Track C filters on it); `instagram_profiles.creator_id` nullable for comment authors.
- Documents `is_sponsored`/`sponsorship_raw_matches` = Track C writes, `is_bot_flagged`/`bot_score` = Track B writes, `brands.source='sponsorship_mention'` only for disclosure extraction.

### `scripts/ingestion/orchestrator.py:88` — core ingestion loop (1460 lines)
- `def recency_cutoff(days: int = DEFAULT_RECENCY_DAYS) -> datetime:` — returns `now - timedelta(days)`, `DEFAULT_RECENCY_DAYS=1095` (3y). Called by `PlatformWorker.__init__`.
- `def load_env():` — reads `../../.env` line-split `k=v`, `env.setdefault(k,v)`. Provides `DATABASE_URL`, `YOUTUBE_API_KEY*`, `OPENCLI_PROFILE`.
- `class Creator:` `@dataclass` with `creator_id: str|None, name, category, youtube_handle, instagram_handle, reddit_handles: list[str], reddit_topic_subs: list[str]` — distinguishes `reddit_handles` (broad feed) vs `reddit_topic_subs` (search only).
- `def mentions_creator(text: str, creator_name: str) -> bool:` — lenient token match, filters `_GENERIC_NAME_TOKENS`, distinctive token `any(t in hay)` else full phrase. Used by `RedditWorker._collect`.
- `class RateLimiter:` `def __init__(self, min_interval_seconds: float = 3.0):` + `def wait(self):` sleep `min_interval - elapsed`. Enforces ~370 calls/h.
- `def _og_exact_int(tok: str):` — strips commas, returns `None` if last char `K/M`, else `int(float(tok))`. Discards rounded counts.
- `def parse_og_description(desc):` — parses `<meta property="og:description">` `"885 likes, 33 comments - nasimamirza on May 9, 2026: \"caption...\""` via `_OG_DATE_RE`, `_OG_COUNT_RE`. Returns `{'date','likes','comments'}`. Backfills past 12-row listing ceiling.
- `def _norm_caption(text):` — collapses markdown link `[txt](url)->txt`, then `re.sub(r"[^a-z0-9]+"," ", lower)`.
- `def own_post_paths(paths, handle):` — filters grid hrefs: if `parts[0].lower()!=handle.lower()` skip foreign collab/tagged post. Prevents attributing `netflix_in` post to `mostlysane`.
- `def match_listing_meta(page_caption, listing):` — joins page caption (full) to `instagram user` listing (100-char truncated) by `_norm_caption` 60-char prefix. Replaces positional `posts_meta[i]`.
- `def caption_key(text):` — `re.sub(r"[^a-z0-9]+"," ", lower)[:60]` if `len>=12` else `None`. Historical prefix key.
- `def run_opencli(*args: str, timeout: int = 30) -> dict | list:` — resolves `_OPENCLI_BIN=shutil.which("opencli")`, retries `_OPENCLI_TRIES=3` with backoff `[5,15]`, does not retry on `429`.
- `def youtube_quota_state() -> str:` — returns `f"key {_yt_key_idx+1} of {len(_YT_KEYS)}"`.
- `def youtube_api_get(endpoint: str, **params) -> dict:` — `GET https://www.googleapis.com/youtube/v3/{endpoint}` with key rotation on `429/403+quota`, sequential not round-robin.
- `def upsert_brand(cur, name: str) -> str:` — `insert into brands (name) values (%s) on conflict (name) do update set updated_at=now() returning brand_id`.
- `def brand_id_for_text(cur, text: str | None) -> str | None:` — picks first `explicit` else first `mention` from `extract_brand_mentions(text)`, calls `upsert_brand`.
- `class PlatformWorker:` — base with `__init__`, `_is_stale`, `_release_on_failure`, `run_batch`, abstract `_handle_for`/`process_creator`.
- `class YouTubeWorker(PlatformWorker):` — `_handle_for -> youtube_handle`; `process_creator`: `youtube_api_get channels forHandle`, upserts `youtube_channels`, `playlistItems uploads`, `videos snippet/statistics`, `to_date` recency filter, inserts `youtube_videos`, then `commentThreads maxResults=100`, inserts `youtube_comments`.
- `class InstagramWorker(PlatformWorker):` — `_handle_for -> instagram_handle`; `process_creator`: `run_opencli instagram profile`, upserts `instagram_profiles`, `instagram user --limit post_cap`, browser scroll collecting `own_post_paths` filtered `a[href*="/reel/"], a[href*="/p/"]`; per `post_url`: `eval _OG_JS` -> `parse_og_description`, `_is_stale`, `extract` -> `parse_caption`, `match_listing_meta`, `brand_id_for_text`, inserts `instagram_posts`, `parse_comments` -> stubs + `instagram_comments`.
- `def _release_session(session: str) -> None:` — best-effort `run_opencli browser <session> close timeout=20`.
- `def enrich_reddit_profile(cur, username: str) -> None:` — `run_opencli reddit user <username> -f yaml`, inserts `reddit_profiles` or stub.
- `class RedditWorker(PlatformWorker):` — `_handle_for` returns first `reddit_handles` else `reddit_topic_subs`; `process_creator` loops both, `_search_retry_empty`, `_collect` via `run_opencli reddit subreddit|search`, filters `mentions_creator` for `topic_search`, inserts `reddit_posts`, `reddit_post_creators`, `_fetch_comments`.
- `def get_connection():` — `psycopg2.connect(ENV["DATABASE_URL"])`.
- `def get_or_create_creator(conn, name: str, category: str, replace_reddit: bool=False, **handles) -> Creator:` — idempotent identity: lookup `youtube_handle` then `instagram_handle`, else Reddit-only fallback `where lower(name)=lower(%s) and instagram_handle is null and youtube_handle is null`, else update coalesce handles.
- `def seed_creators(conn, target_list: list[dict]) -> dict[str, Creator]:` — iterates curated JSON entries, calls `get_or_create_creator(..., replace_reddit=True)`.
- `def load_creator_by_instagram_handle(conn, handle: str) -> Creator | None:` — `select ... where lower(instagram_handle)=lower(%s)`.
- `def main():` — argparse `--seed/--platform/--handles/--target-list/--dry-run/--post-cap/--recency-days`; seeds or builds creators, instantiates `WORKERS[platform]` and `run_batch`.

### `scripts/ingestion/pair_count.py:92`
- `def compute(cur) -> dict:` — sole canonical pair definition: CTEs `EVENTS` (`instagram_posts where is_sponsored OR has_paid_partnership_label + youtube_videos where is_sponsored + reddit_posts where is_sponsored`, all `posted_at not null`), `PAIRS distinct x.creator_id as a, c2.creator_id as b`, `BEFORE/AFTER` counts sum across 3 platform tables where `posted_at < > e.posted_at`. Returns `computable_pairs (n_before>0 and n_after>0)`, 4 readings, fail buckets.
- `def main() -> None:` — connects, `s = compute(cur)`, prints four readings + failures, `--json`/`--why`.

### `scripts/ingestion/collab_edges.py:89`
- `def load_env():` — reads `../../.env`.
- `def run_opencli(*args, timeout=90):` — `env["OPENCLI_PROFILE"]` + `subprocess.run`, yaml.
- `def analyse_post(post_id: str, stored_username: str) -> dict | None:` — `browser collabx open https://instagram.com/p/{post_id}/`, `extract`, asserts `post_id in url`, splits header/body, coauthors via `_LINK`+`_PIC`, primary via `_AGE_AUTHOR`, caption via `parse_caption`.
- `def main():` — queries `instagram_posts where creator_id not null`, iterates with `POST_GAP_SECONDS=8`, aborts on `MAX_CONSECUTIVE_FAILURES=5` or `429`; updates `has_paid_partnership_label`, inserts `creator_related_accounts (creator_id, platform='instagram', handle, relation_type='frequent_collaborator') on conflict do nothing`, checkpoints, classifies new coauthors via `account_classify` + `sheets_sync`.

### `scripts/ingestion/account_classify.py:56`
- `def _words(*terms: str) -> re.Pattern:` — word-boundary alternation `(?<!\w)(?:|...) (?!\w)`.
- `def classify_from_profile(name: str, bio: str, handle: str = "", known_orgs: set[str] | None = None) -> tuple[str, str]:` — ordering: `BRAND_STRONG/_COMMERCE/_PHRASE` -> `ATHLETE_STRONG` -> `_INSTITUTION` -> `_TEAM_STRONG` -> `_LEAGUE` -> `_TEAM` -> `_ATHLETE` -> `_FITNESS` -> `_LIFESTYLE` -> `_BRAND_SYMBOL/_PRODUCT_NOUNS` -> `known_orgs` -> `_SPORT_CONTEXT` -> glued `@mention` -> `other`.
- `def _run(args: list[str], timeout: int = 60) -> subprocess.CompletedProcess:` — `subprocess.run([_OPENCLI,*args])`.
- `def fetch_profile(handle: str) -> dict | None:` — `instagram profile <handle> -f yaml` else browser `meta[name=description]`.
- `def fetch_grid(handle: str, max_chars: int = 12000) -> list[str]:` — `browser open https://instagram.com/{handle}/ extract`, regex `![](alt)(fbcdn url)` -> `alts[:25]`.
- `def grid_relevance(alts: list[str]) -> tuple[int, int, float]:` — counts `_DOMAIN.search(a)`.
- `def load_known_orgs(conn) -> set[str]:` — `select lower(instagram_handle) from creators where category in ('team','league')`.
- `def classify_handle(handle: str, known_orgs: set[str] | None = None, use_grid: bool = True) -> dict:` — `fetch_profile` -> `classify_from_profile`; if `BRAND` return else `fetch_grid` + `grid_relevance`.

### `scripts/ingestion/populate_edges.py:51`
- `def load_env():` / `def run_opencli(*args, timeout=90):` — env + yaml wrapper.
- `def scrape_team_captions(conn, limit_posts=6):` — selects `category='team'`, browser `find --css 'a[href*="/reel/"],a[href*="/p/"]'`, per `post_id` `open/extract` verify, `parse_caption`.
- `def main():` — builds `known={lower(handle):creator_id}`; candidates from `instagram_posts` regex `_MENTION` filtered `h in known`, plus `scrape_team_captions`; dedup `unique={(cid,h)}`; inserts `creator_related_accounts`.

### `scripts/ingestion/sheets_sync.py:43`
- `def _retry(fn, *args, _label: str="", _tries: int=4, **kwargs):` — retries only `ConnectionReset` with `2**attempt`.
- `def _client() -> gspread.Client:` — `Credentials.from_service_account_file(KEY_PATH)`.
- `def _worksheet():` — `client.open_by_key(SHEET_ID).sheet1` (`1UX9K3...`).
- `def read_rows() -> list[dict]:` — `get_all_records()`.
- `def read_approval_counts() -> dict[str, int]:` — counts `accepted/rejected/blank`.
- `def append_brand_signal(instagram_handle: str, signal: str, dry_run: bool=False) -> bool:` — finds row by handle, semicolon-split dedup, `ws.update`.
- `def update_category(updates: dict[str,str], dry_run: bool=False) -> int:` — resolves `category` col, `batch_update` chunked 100.
- `def push_candidates(rows: list[dict] | None=None) -> int:` — reads `candidate_staging.json` if `None`, loads live header, `existing={(instagram_handle).lower()}`, builds `row_fields` per header order, `next_row=len(get_all_values())+1`, `ws.update(f"A{next_row}:{last_col}{last_row}")`.

### `scripts/ingestion/promote_candidates.py:45`
- `def clean(value) -> str | None:` / `def parse_list(value) -> list[str]:` — strip, `lower in {null,none,[]}` -> `None`, `json.loads` if clean.
- `def main():` — `--dry-run/--handles/--exclude`; filters `approval_status==accepted`, applies `blocked`/`wanted` filters; coerces `category` to `other` if invalid, skips if both handles null, calls `get_or_create_creator`, if `follower_count.isdigit()` inserts `instagram_profiles`.

### `scripts/ingestion/discover_candidates.py:65`
- `def with_retry(fn, *args, label: str="", **kwargs):` — 3 attempts 60s apart.
- `def run_opencli(*args: str, timeout: int=60) -> dict | list:` — yaml.
- `def find_post_author(markdown: str) -> str | None:` — `_AUTHOR_LINK` search.
- `def discover_post_links_from_tag(tag: str, session: str, max_posts: int) -> list[str]:` — `browser disc_{tag} open https://instagram.com/explore/tags/{tag}/ wait2 find --css 'a[href*="/reel/"],a[href*="/p/"]'`.
- `def author_for_post(post_path: str, session: str) -> str | None:` — `browser open https://instagram.com{post_path} wait2 extract -> find_post_author`.
- `def relevance_reason(bio: str, category: str) -> tuple[str, bool]:` — bio checks `EXCLUDE_BIO_SIGNAL`, `EXCLUDE_INSTITUTIONAL_SIGNAL`, else `RELEVANCE_KEYWORDS`, else generic hashtag.
- `def profile_check(handle: str) -> dict | None:` — `instagram profile`, `followers <5000 => None`, `india_signal`.
- `def load_known_handles() -> set[str]:` — union from `target_list.json` + `candidate_staging.json`.
- `def load_staging() -> list[dict]:` / `def save_staging(rows: list[dict]) -> None:` — JSON.
- `def discover(tags: list[str], max_posts_per_tag: int, category_hint: str) -> tuple[list[dict], list[str]]:` — per tag grid, per post `author_for_post`, dedup, `profile_check`, `relevance_reason`, `classify_handle`, stages row via `sheets_sync`.

### `scripts/ingestion/brand_extraction.py:55`
- `class BrandMention: @dataclass candidate_name, matched_phrase, confidence: 'explicit'|'mention'`
- `def extract_brand_mentions(text: str) -> list[BrandMention]:` — iterates `_EXPLICIT_PATTERNS` (`in partnership with|sponsored by|...` + `_BRAND_NAME` 1-3 caps), returns explicit first else `@mention` if `#ad` present.

### `scripts/ingestion/backfill_real_names.py:58`
- `def _keepable(ch: str) -> bool:` — `L,M,N` keep, drops ZWJ.
- `def clean_name(raw: str) -> str:` — splits on `_SUFFIX_SEPS`, maps keepable, `re.sub(r"[_.]+"," ",...)`.
- `def load_done() -> dict:` / `def save_done(done: dict) -> None:` — JSON checkpoint.
- `def main() -> None:` — queries `GATED` handle-named creators, `fetch_profile` -> `clean_name` -> `looks_like_real_name` -> `update creators set name`, `update instagram_profiles`.

### `scripts/ingestion/backfill_meta_by_caption.py:43`
- `def norm(s: str) -> str:` — `re.sub(r"\s+"," ", lower) -> re.sub(r"[^a-z0-9 ]","", )[:180]`
- `def fetch_listing(handle: str, limit: int) -> list[dict]:` — `opencli instagram user <handle> --limit <limit> -f json`.
- `def main() -> None:` — per handle fetches listing, builds `by_caption={norm(cap):(pid,dt,likes,cmts)}`; fills null `posted_at/like_count/comment_count` where caption norm matches; reports dated/conflict.

### `scripts/ingestion/backfill_dates_from_shortcode.py:65`
- `def decode(shortcode: str):` — base64 `ALPHABET="A-Za-z0-9-_"` → `media_id` → `datetime.fromtimestamp(((media_id>>23)+1314220021721)/1000,UTC)`. `SHIFT=23` fitted 789/881 within 24h median 0.5d.
- `def self_check(cur) -> float:` — counts `abs(d-when)<=72h` agreement; gate `MIN_AGREEMENT=0.95`.
- `def main() -> None:` — aborts if `<0.95`; fills `posted_at is null` via `decode`.

### `scripts/ingestion/backfill_dates_from_og.py:59`
- `def oc(*args, timeout=120):` — `subprocess.run([opencli,browser,ogdates,*args])`.
- `def og_date(post_id: str):` — `browser open https://instagram.com/p/{post_id}/ wait4 eval og:description`, regex `OG_DATE on Month D, YYYY`.
- `def main() -> None:` — `select post_id where posted_at is null [and is_sponsored|paid]`, per post `og_date`, abort on 5 consecutive fail, `update posted_at`.

### `scripts/ingestion/backfill_dates_from_grid.py:53`
- `def oc(*args, timeout=150):` — browser `griddates` session.
- `def grid_dates(handle: str, scrolls: int) -> dict[str, datetime.date]:` — `open https://instagram.com/{handle}/ wait5`, loop `scrolls` times `extract` regex `![alt](fbcdn) -> /user/(p|reel)/pid`, date `"%B %d, %Y"`, `scroll down`.
- `def main() -> None:` — per handle `grid_dates`, `update posted_at` where null, never overwrites.

### `scripts/ingestion/backfill_captions.py:69`
- `def load_env():` / `def run_opencli(*args, timeout=90):` — env + yaml.
- `def fetch_caption(post_id: str, username: str) -> tuple[str | None, str | None]:` — `browser capbackfill open https://instagram.com/p/{post_id}/ extract` verify, `parse_caption`.
- `def main():` — `select post_id, username, coalesce(length(caption),-1) order by length asc`; per row `fetch_caption`, `update` where new longer.

### `scripts/ingestion/backfill_brand_ids.py:54`
- `def propose_brand_candidates(caption: str) -> list[str]:` — regex `[#tag]` + `[@mention]`, filters `GENERIC_TAGS`, corroborated `re.search(clean in body)` sort first.
- `def load_env():` / `def main():` — counts `where is_sponsored`, iterates `where is_sponsored and brand_id is null`, lookups `REVIEWED` dict hand-verified 8 brands, `insert into brands on conflict` + `update brand_id`.

### `scripts/ingestion/instagram_comment_extract.py:52`
- `class ExtractedComment: comment_id, author_username, text, like_count`
- `def parse_comments(markdown: str) -> list[ExtractedComment]:` — finds `_COMMENT_PERMALINK /c/(\d+)/`, segments, last `_USERNAME_LINK` in `preceding[-400:]` as author, `_LIKE_COUNT` in segment, first non-like non-Reply as body.
- `def parse_caption(markdown: str, username: str) -> str | None:` — regex `_CAPTION_RE_TMPL`, collapses whitespace. Bypasses 100-char truncation.

### `scripts/ingestion/loop_stats.py:34`
- `def main() -> None:` — per-platform **attempted** coverage: Instagram `exists instagram_posts or instagram_profiles.creator_id`, YouTube `CID in yt_discovery_checkpoint or youtube_handle`, Reddit `exists reddit_post_creators or reddit_topic_subs/reddit_handles`, plus `rd_name_gated` and `rd_untouched`. Delegates pair count to `pair_count.compute`.

### `scripts/ingestion/measure_reddit_recency.py:42`
- `def oc_search(query: str, sub: str, limit: int) -> list:` — `reddit search <query> --subreddit <sub> --sort new --limit <limit> -f json`.
- `def mentions(post: dict, name: str) -> bool:` — word-boundary split `re.split name` parts.
- `def age_days(post: dict, now: datetime.datetime):` — tries `created_utc/created/posted_at/date`.
- `def main() -> None:` — samples `select name,reddit_topic_subs`, for each `sub[:2]` `oc_search`, buckets `[(0,90)...(1095,100000)]` counts `rel/tot/undated`, prints relevance % per bucket.

### `scripts/ingestion/resolve_names_wikipedia.py:51`
- `def letters(s: str) -> str:` — `re.sub(r"[^a-z]","",lower)`.
- `def wiki_search(query: str, limit: int=3) -> list[str]:` — `GET https://en.wikipedia.org/w/api.php?action=opensearch&search=...`.
- `def verifies(handle: str, title: str) -> bool:` — `letters(handle)==letters(title) or letters(title).startswith(letters(handle))`.
- `def resolve(handle: str):` — tries `handle` then `letters(handle)`, `verifies` each title.
- `def main() -> None:` — queries `GATED`, `resolve` each -> `looks_like_real_name` -> `update creators set name`.

### `scripts/ingestion/reattribute_posts.py:46`
- `def main() -> None:` — loads `ownership_audit_checkpoint.json` where `real!=stored`, per `post_id` `select username,creator_id`, `insert instagram_profiles(username) do nothing`, `update instagram_posts set username, creator_id` (or `NULL` for non-creators).

### `scripts/ingestion/push_checkpoint_candidates.py:47`
- `def _load_routed() -> set[str]:` / `def _save_routed(routed: set[str]) -> None:` — `routed_brands.json`.
- `def main() -> None:` — loads `coauthor_checkpoint.json` or DB `group by lower(handle)`, loads `creators lower set` + `known_orgs` + `on_sheet`, `pending = checkpoint - creators - on_sheet - routed`; per `h` `classify_handle` -> `BRAND` `append_brand_signal` else push `push_candidates`.

### `scripts/ingestion/merge_duplicate_creator.py:47`
- `def counts(cur, cid):` — counts 6 `creator_id` tables.
- `def main() -> None:` — `--keep/--dup/--apply` validates names lower equal, logs counts, deletes redundant `reddit_post_creators` (`exists keep post_id`), updates `MOVE=(reddit_post_creators,reddit_posts,instagram_posts,youtube_videos) set creator_id=keep`, verifies, `delete from creators where creator_id=dup`.

### `scripts/ingestion/discover_youtube_handles.py:53`
- `def _norm(s: str) -> str:` — `re.sub(r"[^a-z0-9]+"," ", lower).strip()`
- `def _tokens(s: str) -> set[str]:` — `{t for t in _norm(s).split() if len(t)>2}`
- `def verify(creator_name: str, instagram_handle: str | None, ch: dict, min_subs: int=1000) -> tuple[bool, str]:` — checks `customUrl`, auto-suffix `-[a-z0-9]{5}|\d{4}`, exact equality `norm(custom).replace(" ","")==norm(name).replace or ==ig` + `subs>=1000 and not auto_suffix`.
- `def load_ckpt() -> dict:` / `def save_ckpt(d: dict) -> None:` — `yt_discovery_checkpoint.json`.
- `def main() -> None:` — selects `where youtube_handle is null`, `youtube_api_get search q=name type=channel` (`SEARCH_COST=100`) + `channels`, verifies, `update creators set youtube_handle`, checkpoints.

### `scripts/ingestion/audit_post_ownership.py:51`
- `def load_seen() -> dict:` / `def save_seen(seen: dict) -> None:` — `ownership_audit_checkpoint.json`.
- `class Disconnected(RuntimeError):` — browser bridge down.
- `def oc(*args, timeout=120):` — `browser ownaudit`.
- `def real_owner(post_id: str) -> str | None:` — `browser open /p/{post_id}/ wait4 eval og:description/url`, verify `post_id in url`, regex `OWNER = r"-\s*([A-Za-z0-9_.]+)\s+on\s+Month"`.
- `def main() -> None:` — `select post_id,username where username not null [and is_sponsored|paid] order by post_id/random()` filtered `not in seen`, per post `real_owner` with `MAX_CONSECUTIVE_UNKNOWN=12` abort.

### `scripts/ingestion/assign_reddit_subs.py:52`
- `def looks_like_real_name(name: str, handle: str | None) -> bool:` — `name non-empty and lower(name)!=lower(handle) and " " in name`.
- `def subs_for(name: str, category: str, connected_names: str) -> list[str]:` — `NO_CONFIDENT_SUB -> []`, `NBA_HINTS -> ["nba"]`, `team: CRICKET? IPL: FOOTBALL?`, `athlete: FOOTBALL?FOOTBALL : CRICKET?CRICKET : ["india","Cricket"]`, `fitness -> ["indianfitness","india"]`.
- `def main() -> None:` — queries `where both reddit arrays empty`; filters `looks_like_real_name`, per eligible `subs_for` -> `update reddit_topic_subs`.

### `scripts/ingestion/eval_account_classify.py:34`
- `def load_sets() -> dict:` — reads `heldout_accounts.json`.
- `def score(rows, orgs) -> tuple[int, int, list]:` — per `r` `classify_from_profile` vs `r["label"]`.
- `def main() -> None:` — `--propose/--verbose`; `propose N` prints candidates unlabeled; else scores each `set*`.

### `scripts/ingestion/test_account_classify.py:84`
- `def main() -> int:` — iterates `CASES = [(handle,name,bio,expected)]` 40+ hand-labelled, `classify_from_profile` -> `hits/misses`, prints `agreement %`.

### `scripts/ingestion/test_get_or_create_identity.py:30`
- `def cleanup(conn):` — `delete from creators where name like '__identitytest__%'`.
- `def main() -> None:` — asserts Reddit-only reuse, shared subreddit not merged, handle-holding not absorbed, cleans.

### Supabase migrations
- `supabase/migrations/20260808163402_init_schema.sql:1` — `pgcrypto`; `creators` (uuid PK, `category` CHECK, `youtube_handle/instagram_handle text`, `reddit_handles text[]`), `creator_related_accounts (id uuid PK, creator_id FK cascade, platform CHECK, handle, relation_type, unique (creator_id,platform,handle))`, `youtube_channels/text PK`+ idx, `youtube_videos/text PK channel_id FK cascade + creator_id FK null + is_sponsored`, `youtube_comments`, `instagram_profiles text PK`+ index, `instagram_posts text PK username FK cascade + creator_id FK null`, `instagram_comments`, `reddit_profiles`, `reddit_posts`, `reddit_comments`, view `creator_sponsorship_events UNION ALL where is_sponsored`.
- `20260809000000_fix_missing_reddit_indexes.sql:1` — `idx_reddit_profiles_creator`, `idx_reddit_posts_author`, `idx_reddit_comments_author`.
- `20260809010000_add_brands.sql:1` — `create table brands (brand_id uuid PK, name unique, category, handles, follower_count, source default 'sponsorship_mention')`, `alter table youtube_videos/instagram_posts/reddit_posts add column brand_id uuid references brands`, indexes `idx_*_videos_brand`, recreate view adding `brand_id`.
- `20260809020000_dedupe_creators.sql:1` — merges duplicate `athleanx`, `create unique index uq_creators_youtube_handle/instagram_handle where not null`.
- `20260810000000_reddit_topic_subs.sql:1` — `alter table creators add column reddit_topic_subs text[] not null default '{}'`.
- `20260810000000_reddit_post_creators_junction.sql:1` — `create table reddit_post_creators (post_id text FK cascade, creator_id uuid FK cascade, primary key (post_id,creator_id))`, backfill.
- `20260811000000_paid_partnership_label.sql:1` — `alter table instagram_posts add column has_paid_partnership_label boolean` (NULL=unobserved, TRUE=paid), index `where true`.

---

## Track B — ML-Core

> Heterogeneous graph: nodes `creator`(1289-dim: 512 CLIP + 768 BERT + 3 metadata + 6 one-hot) / `brand`(9-dim); edges `collaborates_with`/`co_occurs_with` (scalar `edge_attr`) + `sponsors`/`sponsored_by` (unweighted). Schema `ml/schema.py:1`. GAT chosen over GraphSAGE (inductive, attention = personalized spillover).

### `ml/bot_detection.py:23`
- `def _clip01(x: float) -> float:` — clamp [0,1].
- `def follower_following_ratio_score(follower_count: int, following_count: int, ratio_threshold: float = 3.0) -> float:` — `following / max(follower,1) / threshold` clipped.
- `def account_age_score(account_age_days: float | None, young_threshold_days: float = 30.0) -> float:` — `None->0`, else `clip(1 - age/threshold)`.
- `def posting_frequency_score(posts_per_day: float, spam_threshold: float = 10.0) -> float:` — `clip(posts_per_day/10)`.
- `def engagement_mismatch_score(engagement_rate: float, follower_count: int, low_engagement_threshold: float = 0.005) -> float:` — `follower<1000->0`, else low engagement.
- `@dataclass class BotSignals:` — `follower_count, following_count, account_age_days, posts_per_day, engagement_rate`.
- `def compute_bot_score(signals: BotSignals, weights: dict[str, float] | None = None) -> float:` — weighted average `DEFAULT_COMPONENT_WEIGHTS={ratio:0.3, age:0.25, posting:0.2, mismatch:0.25}`.
- `def is_bot_flagged(bot_score: float, threshold: float = 0.6) -> bool:` — `>=0.6`.

### `ml/causal_regularization.py:22`
- `class PropensityScoreModel(nn.Module):` — `__init__(self, in_dim: int, hidden_dim: int | None = None):` `Linear(in,1)` or `Sequential(Linear,ReLU,Linear)`; `forward(self, x: torch.Tensor) -> torch.Tensor:` `sigmoid(net(x)).squeeze(-1)` in (0,1).
- `def overlap_penalty(propensity: torch.Tensor, eps: float = 0.05) -> torch.Tensor:` — mean `(eps-p).clamp² + (p-(1-eps)).clamp²`.
- `def doubly_robust_weights(treatment: torch.Tensor, propensity: torch.Tensor, clip_eps: float = 0.05) -> torch.Tensor:` — `treatment/p + (1-treatment)/(1-p)` clamped.
- `def laplacian_smoothness_penalty(node_values: torch.Tensor, edge_index: torch.Tensor, edge_weight: torch.Tensor) -> torch.Tensor:` — `mean(weight*(f_u-f_v)²)`, empty→0.
- `def has_sponsored_neighbor(collab_edge_index: torch.Tensor, creator_is_sponsored: torch.Tensor) -> torch.Tensor:` — `result[dst[sponsored]]=True`.
- `def consistency_penalty(exposure: torch.Tensor, has_sponsored_neighbor: torch.Tensor) -> torch.Tensor:` — `mean(exposure[~has]²)`.

### `ml/dummy_data.py:19`
- `def make_dummy_hetero_data(num_creators: int = 6, num_brands: int = 3, avg_degree: int = 3, seed: int = 0) -> "HeteroData":` — seeded `creator.x ~ N(0,1)` (N,1289), `brand.x` (M,9); `symmetric_weighted_edges` via `torch.combinations` uniform weight both directions; `avg_degree` → `num_pairs = N*avg_degree//2`.
  - `def symmetric_weighted_edges(n: int, num_pairs: int):` inner — symmetric same weight.

### `ml/evaluation.py:19`
- `@dataclass class EvaluationReport: mae, rmse, r2, calibration_slope, calibration_intercept, n`
- `def _linear_fit(x: torch.Tensor, y: torch.Tensor) -> tuple[float, float]:` — `slope = sum((x-xm)*(y-ym))/sum((x-xm)²)`.
- `def evaluate_predictions(predictions: torch.Tensor, targets: torch.Tensor) -> EvaluationReport:` — `mae, rmse, r2, _linear_fit`, shape check, n=0 → NaN.

### `ml/exposure.py:20`
- `class ExposureModule(nn.Module): __init__(self, in_channels: int, hidden_channels: int = 16, heads: int = 1):` wraps `GATConv(in, hidden, heads, concat=False, add_self_loops=False)`; `forward(self, x: torch.Tensor, edge_index: torch.Tensor, treatment: torch.Tensor) -> torch.Tensor:` empty→zeros else `GATConv(..., return_attention_weights=True)` → `alpha*treatment[src]` index_add into dst.

### `ml/feature_extraction.py:46`
- `@dataclass class RawCreatorRecord: category_one_hot, log_subscriber_count|None, engagement_rate|None, reputation_score|None, raw_text, thumbnail_urls`
- `class FeatureExtractor: __init__(self, max_thumbnails: int = 5, device: str | None = None):` loads `CLIPModel/Processor(openai/clip-vit-base-patch32)` + `BertTokenizer/Model(bert-base-uncased)`; `_clip_embedding(self, thumbnail_urls: list[str]) -> torch.Tensor:` mean-pooled CLIP or zeros(512); `_bert_embedding(self, raw_text: str) -> torch.Tensor:` BERT pooled or zeros(768); `extract(self, record: RawCreatorRecord) -> torch.Tensor:` concats `[clip(512), bert(768), metadata(3+6)]` → (1289,).

### `ml/gail_loss.py:26`
- `@dataclass class GAILLossWeights: prediction=1.0, overlap=0.1, smoothness=0.1, consistency=0.1`
- `def compute_gail_loss(predicted_spillover: torch.Tensor, target_spillover: torch.Tensor, propensity: torch.Tensor, collab_edge_index: torch.Tensor, collab_edge_weight: torch.Tensor, has_sponsored_neighbor_mask: torch.Tensor, weights: GAILLossWeights | None = None, prediction_mask: torch.Tensor | None = None, treatment: torch.Tensor | None = None) -> tuple[torch.Tensor, dict[str, float]]:` — `prediction MSE (+ DR weighting) + overlap + smoothness + consistency`. `prediction_mask` restricts supervised term only; do not pre-subset tensors.

### `ml/gail_model.py:19`
- `class GAILModel(nn.Module): __init__(self, creator_feature_dim: int, hidden_channels: int = 16, heads: int = 2):` wires `SchemaSmokeTestGAT` + `ExposureModule` + `PropensityScoreModel` + `SpilloverPredictionHead`; `forward(self, data: HeteroData, treatment: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:` backbone → embeddings; exposure; propensity from `data["creator"].x`; prediction_head(embeddings, exposure).

### `ml/inference.py:56`
- `class IsolatedCreatorError(ValueError):` — degree 0 on both `collaborates_with`+`co_occurs_with`.
- `def _t_critical(df: int) -> float:` — lookup `_T_TABLE` t_{0.975,df} (df8→2.306, >30→1.96).
- `def _load_checkpoint(ckpt_path: str | Path) -> dict:` — `torch.load(...,weights_only=False)` or FileNotFoundError.
- `def _build_data(ckpt: dict):` — reconstructs `HeteroData` from `ckpt["tensors"]`.
- `def _ensure_loaded(ckpt_path: str | Path | None = None) -> dict:` — singleton cache; builds `GAILModel`, loads `state_dict`, single forward caches `preds`; degree via distinct neighbor count; `base_hw = max(t*residual_std*sqrt(1+1/N),0.15)`, `inferred_hw = max(base*1.6,0.25)`, N=10, mse1.84 → base≈3.28 inferred≈5.25.
- `def load_predict(creator_id: str, checkpoint_path: str | Path | None = None) -> Dict[str, float | str]:` — `{spillover_score, basis:"trained"|"inferred", confidence_low/high}`; raises `KeyError`/`IsolatedCreatorError`/`FileNotFoundError`.
- `def load_predict_batch(creator_ids: List[str], ...) -> List[Dict]:` — ordered, isolated/unknown as dict with `error` not raise.
- `predict = load_predict` alias; `def get_model_info(checkpoint_path: str | Path | None = None) -> dict:` — git_sha, pair_count, graph, training_stats.

### `ml/model.py:31`
- `class SchemaSmokeTestGAT(nn.Module): __init__(self, hidden_channels: int = 32, heads: int = 2):` builds `HeteroConv` dict per `EDGE_TYPES` `GATConv((-1,-1), hidden, heads, concat=False, edge_dim=1 if weighted)`; `forward(self, data: HeteroData) -> dict[str, torch.Tensor]:` `conv1(x_dict,edge_index_dict,edge_attr_dict)` sum aggr; ReLU.

### `ml/schema.py:78`
- `def empty_hetero_data() -> HeteroData:` — zero-node HeteroData `creator 1289`, `brand 9`, empty edge_index (2,0) + edge_attr (0,1).

### `ml/spillover_head.py:16`
- `class SpilloverPredictionHead(nn.Module): __init__(self, embedding_dim: int, hidden_dim: int = 16):` `Sequential(Linear(emb+1, hidden),ReLU,Linear(hidden,1))`; `forward(self, embeddings: torch.Tensor, exposure: torch.Tensor) -> torch.Tensor:` `cat([embeddings, exposure.unsqueeze]) -> net -> squeeze`.

### `ml/training.py:22`
- `@dataclass class TrainConfig: epochs=100, lr=1e-2, val_fraction=0.2, seed=0, loss_weights`
- `def train_val_split(num_nodes: int, val_fraction: float, seed: int) -> tuple[torch.Tensor, torch.Tensor]:` — seeded `randperm`, `n_val = clamp(round(N*frac),0,N-1)`.
- `def _indices_to_mask(indices: torch.Tensor, num_nodes: int) -> torch.Tensor:` — bool mask.
- `def train(model: GAILModel, data: HeteroData, treatment: torch.Tensor, target: torch.Tensor, config: TrainConfig | None = None) -> list[dict]:` — transductive: full graph forward, supervised MSE masked `train_mask`, structural terms full graph; `compute_gail_loss(... prediction_mask=train_mask)`, Adam, `val_loss` on `val_idx`.

### `ml/weighted_sage_conv.py:22`
- `class WeightedSAGEConv(MessagePassing): aggr="mean"` — `__init__(self, in_channels: int, out_channels: int):` two Linears; `forward(self, x, edge_index, edge_weight)` `propagate` then `lin_self+lin_neigh`; `message(self, x_j, edge_weight) -> torch.Tensor:` `x_j * weight`.

### `scripts/build_real_hetero_data.py:60`
- `def load_creator_features(path: str, extractor: FeatureExtractor) -> tuple[torch.Tensor, dict[str, int], list[str]]:` — JSON → `RawCreatorRecord` → `extractor.extract` stack.
- `def load_symmetric_edges(path: str, id_to_index: dict[str, int]) -> tuple[torch.Tensor, torch.Tensor]:` — stack `[src,dst]`, weight `[[w]]`.
- `def load_brands(database_url: str) -> tuple[torch.Tensor, dict[str, int]]:` — `psycopg2` `brands`, metadata `[log1p follower, log1p post, verified, num_platforms] + 5 zeros`.
- `def load_sponsorship_edges(path: str, creator_id_to_index: dict, brand_id_to_index: dict) -> tuple[torch.Tensor, torch.Tensor]:` — maps ids to indices.
- `def load_treatment(database_url: str, creator_id_to_index: dict, num_creators: int) -> torch.Tensor:` — `1.0` for any `creator_sponsorship_events` distinct creator.
- `def load_real_targets(computable_pairs_path: str, creator_id_to_index: dict, num_creators: int) -> tuple[torch.Tensor, list[dict]]:` — `computable_pairs.json` `lift=(after-before)/(before+1)` mean per neighbor.
- `def report_structure(data, id_to_name: dict[int, str]) -> None:` — NetworkX degree/isolates/components per type.
- `def main() -> int:` — CLI 5 JSON paths + `DATABASE_URL`; builds HeteroData, GAT forward + inductive check, builds treatment/target, runs `GAILModel` 50 epochs.

### `scripts/compute_training_pair_deltas.py:47`
- `def platform_engagement(cur, creator_id: str, platform: str, event_date):` — `SELECT date,e1,e2 WHERE creator_id AND date NOT NULL AND e1 NOT NULL AND e2 NOT NULL`; splits `before = e1+e2 if d<event`, `after` similarly; both-cols-non-null fix.
- `def main() -> int:` — imports `pair_count.CANDIDATES`, good_rows where straddle >0 both sides, per platform `lift=(after_avg-before_avg)/(before_avg+1)`, writes `training_pair_deltas.json`.

### `scripts/find_computable_training_pairs.py:38`
- `def norm(h: str) -> str:` — `lower, strip, strip @/u//r/`.
- `def resolved_pairs(cur) -> dict[str, set[str]]:` — resolves `creator_related_accounts` via `creators` handle maps, dropping ambiguous.
- `def content_dates_and_engagement(cur, creator_id: str, platform: str, event_date) -> dict:` — `SELECT date, coalesce(e1,0)+coalesce(e2,0)` with all dated posts, splits before/after (older coalesce version).
- `def main() -> int:` — reads `creator_sponsorship_events`, for each with `posted_at` and neighbors, checks every platform, `COMPUTABLE` if `n_before>0 and n_after>0` on same platform; writes `computable_pairs.json`.

### `scripts/train_holdout_round3.py:67`
- `def load_real_targets_from_deltas(deltas_path: str, creator_id_to_index: dict, num_creators: int) -> tuple[torch.Tensor, dict[str, list[float]]]:` — reads `training_pair_deltas.json` mean lift per `neighbour_id`.
- `def leave_one_out_eval(data, treatment: torch.Tensor, target: torch.Tensor, labeled_idx: list[int], base_seed: int = 0) -> list[dict]:` — LOO per fold fresh `GAILModel`, `train_mask[held_out]=False`, Adam 50 epochs `compute_gail_loss` with `prediction_mask`, records `held_out_prediction/target/sq_err/propensity`.
- `def main() -> int:` — loads CLIP+BERT, builds real HeteroData live (259 creators), GAT + inductive checks, builds treatment/target, runs LOO, reports mean MSE 67.19 vs 67.36 baseline, propensity saturation.

### `scripts/train_prod_model.py:50`
- `def load_env() -> dict:` — loads `.env` from repo root or `track-a-data-infra/.env`.
- `def get_git_sha() -> str:` — `git rev-parse HEAD`.
- `def category_one_hot(category: str | None) -> list[int]:` — 6-dim one-hot.
- `def compute_feature_scaler(x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:` — per-dim `mean/std` (clamp 1e-6).
- `def platform_engagement(cur, creator_id: str, platform: str, event_date):` — both-cols-non-null.
- `def build_targets_from_canonical(cur, creator_id_to_index: dict, num_creators: int):` — `pair_count.compute(cur)` → good_rows → per-creator mean lift.
- `def build_creator_features(cur, extractor: FeatureExtractor):` — DB-direct: `creators` + `youtube_channels` + `instagram_profiles` + 20 videos/posts, `log_subscriber_count=log1p(max(yt subs, ig followers))`, `engagement_rate`, `raw_text`, `thumbnails` → `RawCreatorRecord` → `extractor.extract`.
- `def load_collab_edges(cur, id_to_index: dict):` — resolves handles, dedup `unordered pair` weights, both directions.
- `def load_cooccurrence_edges(cur, id_to_index: dict):` — `reddit_post_creators` combinations per post, both directions.
- `def load_brands(cur):` — brand metadata same as build script.
- `def load_treatment(cur, id_to_index: dict, num_creators: int):` — distinct sponsored creators → treatment.
- `def main() -> int:` — seed 0; `x_norm=(x-mean)/std`; `GAILModel(1289,16,2)` train once on all 10 nodes 100 epochs with `prediction_mask=labeled_idx` + DR weights; save `models/gail_checkpoint.pt` (3.7 MB) + `feature_scaler.json` + `training_pair_ids.json`.

### `scripts/validate_gat_on_real_data.py:31`
- `def load_real_creator_features(creators_json_path: str, extractor: FeatureExtractor) -> tuple[torch.Tensor, dict[str, int]]:` — JSON → `RawCreatorRecord` → `extractor.extract`.
- `def main() -> int:` — expects `creators.json collab_edges.json`; Test A real features+real edges via `make_dummy_hetero_data(avg_degree=0)` override; Test B same model +10 synthetic nodes inductive.

### `scripts/verify_environment.py:15`
- `def main() -> int:` — prints torch/geometric versions, CUDA, trivial matmul, `GATConv` forward, `HeteroData`.

### `tests/test_bot_detection.py:14`
- `test_follower_following_ratio_score_low_for_balanced_account` — balanced 5000/800 <0.3
- `test_follower_following_ratio_score_high_for_mass_follower` — 100/5000 ==1.0
- `test_follower_following_ratio_score_rejects_negative_counts` — ValueError
- `test_account_age_score_zero_for_old_account` — 1000 ->0
- `test_account_age_score_high_for_brand_new_account` — 1 -> >0.9
- `test_account_age_score_zero_when_unavailable...` — None->0
- `test_posting_frequency_score_low_for_normal_cadence` — 1.5 <0.2
- `test_posting_frequency_score_high_for_spam_cadence` — 50==1.0
- `test_engagement_mismatch_score_ignored_for_small_accounts` — 500 followers ->0
- `test_engagement_mismatch_score_high_for_large_account_low_engagement` — 0.0001/500k >0.9
- `test_engagement_mismatch_score_zero_for_healthy_engagement` — 0.05 ->0
- `test_compute_bot_score_low_for_normal_account` — <0.3 not flagged
- `test_compute_bot_score_high_for_obvious_bot` — >0.8 flagged
- `test_compute_bot_score_instagram_missing_age_still_flags...`

### `tests/test_causal_regularization.py:15`
- `test_propensity_model_output_in_unit_interval` — MLP shape (10,) in [0,1]
- `test_propensity_model_plain_logistic_regression_variant` — hidden None shape (5,)
- `test_overlap_penalty_zero_when_scores_centered` — all 0.5 ->0
- `test_overlap_penalty_positive_for_extreme_scores` — 0.001/0.999 -> >0
- `test_doubly_robust_weights_matches_manual_calc`
- `test_doubly_robust_weights_clips_extreme_propensity` — 0.0 clipped finite
- `test_laplacian_smoothness_penalty_zero_for_constant_values`
- `test_laplacian_smoothness_penalty_positive_for_varying_values`
- `test_laplacian_smoothness_penalty_zero_not_nan_for_empty_edges` — empty ->0 not NaN
- `test_has_sponsored_neighbor_and_consistency_penalty_hand_built_graph`

### `tests/test_evaluation.py:7`
- `test_perfect_predictions_give_ideal_metrics` — mae0 rmse0 r2 1 slope1 intercept0 n4
- `test_known_mae_and_rmse_values` — mae3.5 rmse sqrt12.5
- `test_empty_inputs_return_nan_not_crash`
- `test_constant_targets_give_nan_r2_not_crash`
- `test_constant_predictions_give_nan_calibration_not_crash`
- `test_shape_mismatch_raises`

### `tests/test_exposure.py:6`
- `test_exposure_zero_when_no_neighbors_are_sponsored`
- `test_exposure_positive_when_a_neighbor_is_sponsored`
- `test_exposure_handles_empty_edge_index_without_crashing`
- `test_exposure_is_symmetric_on_a_fully_symmetric_graph`

### `tests/test_feature_extraction.py:12`
- `extractor()` fixture `FeatureExtractor(max_thumbnails=2)`; `_fake_jpeg_bytes()` 64x64 RGB; `class _FakeResponse:` mock; `test_bert_embedding_shape` (768,); `test_bert_embedding_zero_for_empty_text`; `test_clip_embedding_shape_with_mocked_thumbnail` (512,); `test_clip_embedding_zero_for_no_thumbnails`; `test_clip_embedding_skips_broken_url_without_crashing`; `test_extract_full_pipeline_handles_real_stub_creator_shape` (1289,) no NaN; `test_extract_full_pipeline_with_populated_creator`.

### `tests/test_gail_loss.py:6`
- `test_combined_loss_shape_and_components` — scalar + 5 keys
- `test_perfect_prediction_symmetric_graph_gives_near_zero_loss` — <1e-6
- `test_zero_weight_isolates_prediction_term_only`
- `test_handles_empty_collaboration_edges_without_nan`
- `test_treatment_arg_applies_doubly_robust_weighting`

### `tests/test_gail_model.py:7`
- `test_forward_pass_shapes` — dummy 6/3, treatment[0]=1 -> prediction/exposure/propensity (6,) no NaN
- `test_forward_pass_with_zero_collaboration_edges`

### `tests/test_schema.py:6`
- `test_empty_hetero_data_has_correct_structure` — (0,1289)/(0,9)
- `test_dummy_hetero_data_is_valid` — validate() passes
- `test_weighted_creator_edges_are_symmetric_with_matching_weight`
- `test_dummy_hetero_data_with_zero_brands_does_not_crash`
- `test_gat_forward_pass_produces_expected_shapes`

### `tests/test_spillover_head.py:6`
- `test_output_shape_and_no_nans`
- `test_handles_all_zero_exposure_without_crashing`
- `test_handles_single_node_graph`
- `test_gradients_flow_back_to_embeddings_and_exposure`

### `tests/test_training.py:8`
- `test_train_val_split_basic` — 10 nodes 20% -> disjoint sum 10
- `test_train_val_split_single_node_leaves_val_empty`
- `test_train_val_split_two_nodes_leaves_at_least_one_train`
- `_sponsored_neighbor_count_target` helper; `test_training_loop_reduces_loss_on_synthetic_target` 80 epochs; `test_training_loop_handles_zero_collaboration_edges`; `test_training_loop_handles_single_node_graph`; `test_training_loop_on_fully_symmetric_dummy_graph`.

### `tests/test_weighted_sage_conv.py:7`
- `test_forward_pass_produces_expected_shape` — (6,16)
- `test_edge_weight_actually_changes_output` — weight 1 vs 5 changes output
- `test_generalizes_to_a_graph_with_more_nodes_without_retraining`

### `models/gail_checkpoint.pt` — structure not functions
- 3.86 MB, keys `state_dict, config, feature_scaler, training_pair_ids, training_pair_details, git_sha, pair_count, graph, tensors, training_stats`; `config {creator_feature_dim:1289, hidden_channels:16, heads:2, epochs:100, lr:0.01, seed:0}`; `feature_scaler {mean, std}` per-dim; `training_pair_ids` 10 distinct UUIDs; `pair_count {computable54, checks138, directed23, undirected19, events_yielding40, events53, collab170, same34, cross20, effective10}`; `graph {num_creators259, num_brands19, collab340, coocc1414, creator_ids_order[259], creator_id_to_name}`; `tensors {creator_x_raw(259,1289), creator_x_norm(259,1289), brand_x(19,9), collab_edge_index(2,340), coocc_edge_index(2,1414), treatment(259,), target(259,)}`; `training_stats {mse_trained1.837, baseline67.363, per_node sorted (Kohli 18.13 dominates), final_prop_mean0.61}`. Consumed by `ml/inference.py` (`load_predict`, `load_predict_batch`, `get_model_info`).

---

## Track C — Fusion+Backend

### `backend/app/main.py:1`
- `def _sanitize_non_finite(obj):28` — recursively replaces NaN/Infinity with repr.
- `async def validation_exception_handler(request, exc):48` — `@app.exception_handler(RequestValidationError)` → `JSONResponse 422` sanitized.
- `def on_startup():53` — `@app.on_event("startup") init_db()` for `fusionscore`, `riskalert`.
- App assembly `12,19,58-64` — `FastAPI(title, version)` + `CORSMiddleware` allowlist `localhost:3000,127.0.0.1:3000`, `allow_credentials=False`.

### `backend/app/config.py:1`
- `class Settings(BaseSettings):6` — `env_file=".env"`, defaults `database_url="sqlite:///./fusion_backend.db"`, `api_key=None`, `fusion_weight_spillover=0.4 / sentiment_risk=0.3 / creator_feature=0.3`, `cors_allow_origins="http://localhost:3000,http://127.0.0.1:3000"`, `api_title/api_version`.
- `@property def cors_allow_origins_list:50` — split `CORS_ALLOW_ORIGINS` into list.

### `backend/app/database.py:1`
- `def init_db():11` — if SQLite `create_all(all)` else `create_all(tables=TRACK_C_OWNED_TABLES)` (never ALTER Track A).
- `def get_session():32` — generator `Session(engine)`.

### `backend/app/feature_store.py:1`
- `def _normalize_handle(handle):74` — `lower().strip().strip @/u//r/`.
- `def _category_one_hot(category):82` — 6-dim one-hot `CREATOR_CATEGORIES`.
- `def _compute_engagement_rate(...):89` — `(likes+comments)/reach` pooled YT+IG, reach via `view_count` + `follower_count`.
- `def build_creator_features(session):115` — queries `creators`+`youtube_channels/instagram_profiles`+`youtube_videos/instagram_posts`; `log_subscriber_count=log1p(max)`, `raw_text = scrub_text(join bio/desc/titles/captions)[:20]`, `thumbnail_urls`, `reputation_score=None`.
- `def build_collaboration_edges(session):179` — two-pass: `handle→creator_ids` drop ambiguous `len!=1`; `where relation_type=="frequent_collaborator"`; `pair_weights[sorted(a,b)]+=1`; emit both directions `weight=float(count)`.
- `def build_co_occurrence_edges(session):243` — `reddit_post_creators` junction `post_id→set(creator_id)` → combinations weight distinct posts both directions.
- `def build_sponsorship_edges(session):275` — union `where is_sponsored==True and brand_id is not None and creator_id is not None` across 3 platform tables → `SponsorshipEdge`.

### `backend/app/fusion.py:1`
- `def compute_fusion_score(...):38` — `final = (w1*spillover + w2*sentiment + w3*creator)*100 + risk_adj`, `risk_adjustment=-10 if sentiment<RISK_THRESHOLD(0.3) else 0`, `final=clamp(0,100)`, `margin=hw*100*w1` else `PLACEHOLDER_CONFIDENCE_MARGIN(8.0)`, `low=max(0,final-margin) high=min(100,final+margin)`. Only w1 variance modeled.

### `backend/app/labeling.py:1`
- `def detect_sponsorship(*texts):40` — regex `combined=" ".join(t for t in texts if t)` `finditer` 11 patterns `#ad\b`, `#sponsored\b`, etc `IGNORECASE`, requires word boundary, returns `(bool(matches), matches)` raw substrings for audit.

### `backend/app/models.py:1`
- `def utcnow():43` — `datetime.now(timezone.utc)`
- `def _string_array_column():47` — `ARRAY(String).with_variant(JSON(), "sqlite")` must be `ARRAY(String)` not `ARRAY(str)`.
- `class Brand:62` — `brands` table `brand_id UUID PK`, `name unique`, `category`, handles, `follower_count/post_count`, `is_verified`, `source="sponsorship_mention"`, `fetched_at/created_at/updated_at`.
- `class Creator:86` — `creators` `creator_id UUID PK`, `name`, `category` CHECK, `youtube_handle/instagram_handle`, `reddit_handles:list[str]`, `notes`.
- `class CreatorRelatedAccount:100` — `creator_related_accounts` `id UUID PK`, `creator_id FK`, `platform youtube|instagram|reddit`, `handle`, `relation_type` (only `frequent_collaborator` resolved).
- `class YouTubeChannel:117` — `youtube_channels` `channel_id PK`, `creator_id? FK`, `channel_handle/title/description`, `subscriber_count`, `channel_created_at/country`, `is_bot_flagged/bot_score`.
- `class YouTubeVideo:137` — `youtube_videos` `video_id PK`, `channel_id FK`, `creator_id?`, `title/description/published_at/thumbnail_url/duration/view_count/like_count/comment_count/tags[]`, `is_sponsored?`, `sponsorship_raw_matches?`, `brand_id?`.
- `class InstagramProfile:159` — `instagram_profiles` `username PK`, `creator_id?`, `full_name/bio`, `follower_count/following_count/post_count`, `is_verified/is_bot_flagged`.
- `class InstagramPost:177` — `instagram_posts` `post_id PK`, `username FK`, `creator_id?`, `caption/posted_at/thumbnail_url/media_type/like_count/comment_count/hashtags[]`, `is_sponsored?`, `sponsorship_raw_matches?`, `has_paid_partnership_label?`, `brand_id?`.
- `class RedditProfile:198` — `reddit_profiles` `username PK`, `creator_id?`, `account_created_at/comment_karma`.
- `class RedditPost:212` — `reddit_posts` `post_id PK`, `subreddit`, `creator_id?`, `author_username FK?`, `title/body/posted_at/score/num_comments`, `is_sponsored?`, `brand_id?`.
- `class RedditPostCreator:231` — `reddit_post_creators` composite PK `(post_id, creator_id)`.
- `class FusionScore:250` — `fusionscore` `id int PK`, `creator_id UUID`, `spillover_score`, `spillover_basis="placeholder"`, `sentiment_risk_score/creator_feature_score/final_score/confidence_low/high/risk_adjustment`, `computed_at`.
- `class RiskAlert:266` — `riskalert` `id int PK`, `creator_id UUID`, `severity low|medium|high`, `reason/source`, `propagated_from_creator_id?`, `created_at`, `resolved bool`.
- `TRACK_C_OWNED_TABLES:282` — `[FusionScore.__table__, RiskAlert.__table__]`

### `backend/app/schemas.py:1`
- `class ScoreBreakdown:21` — 6 fields `spillover_score/sentiment_risk_score/creator_feature_score` + `weight_*`.
- `class BrandRecommendationRequest:32` — `product_category, budget gt0 allow_inf_nan=False, target_region/demographic?, platform_preference?, max_results 1-50`.
- `SpilloverBasis:41` — `Literal["trained","inferred","placeholder","isolated"]`.
- `class InfluencerRecommendation:44` — `creator_id UUID, name/category/handles, final_score/confidence_low/high 0-100, spillover_basis, estimated_reach/cost, score_breakdown`.
- `class BrandRecommendationResponse:60` — `query, results, is_mock_data`.
- `class CreatorIngest:78` — mirrors `Creator`.
- `class CreatorRelatedAccountIngest:88` — `creator_id/platform/handle/relation_type`.
- `class YouTubeChannelIngest:95` / `YouTubeVideoIngest:108` / `InstagramProfileIngest:125` / `InstagramPostIngest:136` / `RedditProfileIngest:151` / `RedditPostIngest:159` — ingest mirrors with optional `is_sponsored`.
- `class IngestionResponse:173` — `received/created/updated`.
- `class FusionScoreComputeRequest:181` — `creator_id, spillover_score? 0-1 (auto), sentiment_risk_score/creator_feature_score 0-1`.
- `class FusionScoreResponse:188` — `creator_id, final_score/confidence_low/high, risk_adjustment, breakdown, spillover_basis, computed_at, is_placeholder_formula`.
- `class AlertCreate:204` — `creator_id, severity low|medium|high, reason, source default "sentiment_propagation", propagated_from_creator_id?`.
- `class AlertResponse:222` — `id, creator_id/severity/reason/source/propagated_from_creator_id?/created_at/resolved`.
- `class LabelingPlatformResult:235` / `LabelingRunResponse:240` — `checked, labeled_sponsored; youtube_videos/instagram_posts/reddit_posts: LabelingPlatformResult`.
- `class CreatorFeatureRecord:250` — `creator_id/name/category/category_one_hot/log_subscriber_count?/engagement_rate?/reputation_score? always None /raw_text/thumbnail_urls/is_stub`.
- `class CollaborationEdge:266` — `source_creator_id/target_creator_id, weight`.
- `class SponsorshipEdge:272` — `creator_id/brand_id, content_id, platform`.
- `class HealthResponse:281` — `status/db_connected/version`.

### `backend/app/spillover.py:1`
- `def _fallback(...):52` — `PLACEHOLDER_SPILLOVER=0.5 PLACEHOLDER_HALF_WIDTH=0.25` → `basis` `placeholder` vs `isolated`.
- `def get_spillover(creator_id):64` — if `not _HAS_GAIL` → placeholder; `try: _load_predict(cid)` → `IsolatedCreatorError→isolated`, `KeyError→isolated`, `FileNotFoundError→placeholder`, else placeholder with log.
- `def get_spillover_batch(creator_ids):99` — `if not _HAS_GAIL` → placeholder per id else `load_predict_batch` → map `isolated/unknown→isolated` else `placeholder`.
- `def get_model_info_safe():146` / `def is_gail_available():157` / `def gail_unavailable_reason():161` — diagnostics.

### `backend/app/text_processing.py:1`
- `def scrub_text(text):17` — `_URL_RE`, `_HTML_TAG_RE`, `_MENTION_RE`, `_WHITESPACE_RE` order → collapse.
- `def normalize_to_utc(dt):33` — naive→UTC, aware→`astimezone(UTC)`.

### `backend/app/auth.py:1`
- `def require_api_key(...):14` — if `not settings.api_key: return`; if `x_api_key != settings.api_key: raise 401`. Protects `POST /ingestion/*`, `POST /scores/compute`, `POST /alerts`, `POST /labeling/run`; GETs + `POST /recommendations` unauthenticated.

### `backend/app/gail/weighted_sage_conv.py:1`
- `class WeightedSAGEConv(MessagePassing): aggr="mean"` — `__init__(in_channels,out_channels)`, `forward(x, edge_index, edge_weight)`, `message(x_j, edge_weight): x_j*weight`. Prototype.

### `backend/app/gail/spillover_head.py:1`
- `class SpilloverPredictionHead(nn.Module): net=Sequential(Linear(emb+1→16),ReLU,Linear(16→1))` — `forward(embeddings, exposure): cat([embeddings, exposure.unsqueeze]) -> net`.

### `backend/app/gail/schema.py:1`
- `def empty_hetero_data():78` — `creator 1289`, `brand 9`, empty `edge_index (2,0)` + `edge_attr (0,1)`.

### `backend/app/gail/model.py:1`
- `class SchemaSmokeTestGAT(nn.Module): __init__(hidden_channels=32,heads=2): HeteroConv per EDGE_TYPES GATConv((-1,-1),hidden,heads,concat=False,edge_dim=1 if weighted)`; `forward(data): conv1(x_dict,edge_index_dict,edge_attr_dict) -> ReLU`.

### `backend/app/gail/inference.py:1`
- `class IsolatedCreatorError(ValueError):56`
- `def _t_critical(df):65` — lookup `_T_TABLE` t_{0.975,df}
- `def _load_checkpoint(ckpt_path):76` — `torch.load(cpu, weights_only=False)` or FileNotFoundError
- `def _build_data(ckpt):85` — reconstructs `HeteroData` from `ckpt["tensors"]`
- `def _ensure_loaded(ckpt_path=None):109` — singleton lazy loader; builds `GAILModel`, loads `state_dict`, single forward caches `preds`; degrees per edge; `base_hw = max(t*residual_std*sqrt(1+1/N),0.15)`, `inferred_hw = max(base*1.6,0.25)`, N=10, mse1.84 → base≈3.28 inferred≈5.25
- `def load_predict(creator_id,checkpoint_path=None):201` — `{spillover_score,basis,confidence_low/high}`; raises `KeyError`/`IsolatedCreatorError`/`FileNotFoundError`
- `def load_predict_batch(creator_ids,...):231` — ordered, isolated/unknown as dict with `error`
- `predict=load_predict:252` alias; `def get_model_info(...):255` — git_sha, pair_count, graph, training_stats

### `backend/app/gail/gail_model.py:1`
- `class GAILModel(nn.Module): __init__(creator_feature_dim,hidden_channels=16,heads=2): backbone=SchemaSmokeTestGAT, exposure_module=ExposureModule, propensity_model=PropensityScoreModel, prediction_head=SpilloverPredictionHead`; `forward(data, treatment): embeddings=backbone(data)["creator"]; exposure=exposure_module(embeddings,collab_edge_index,treatment); propensity=propensity_model(data["creator"].x); prediction=prediction_head(embeddings,exposure)`.

### `backend/app/gail/exposure.py:1`
- `class ExposureModule(nn.Module): __init__(in_channels,hidden_channels=16,heads=1): attn_conv=GATConv(in,hidden,heads=1,concat=False,add_self_loops=False)`; `forward(x,edge_index,treatment): if empty → zeros else (_,alpha)=attn_conv(...,return_attention_weights=True); alpha=mean if multi-head; weighted_treatment=alpha * treatment[src]; exposure.index_add_(0,dst,weighted_treatment)`.

### `backend/app/gail/causal_regularization.py:1`
- `class PropensityScoreModel(nn.Module): __init__(in_dim,hidden_dim=None): Linear or Sequential(ReLU)`; `forward(x): sigmoid(net(x)).squeeze`
- `def overlap_penalty(propensity,eps=0.05): mean((eps-p).clamp² + (p-(1-eps)).clamp²)`
- `def doubly_robust_weights(treatment,propensity,clip_eps=0.05): treatment/p + (1-treatment)/(1-p) clamped`
- `def laplacian_smoothness_penalty(node_values,edge_index,edge_weight): mean(weight*(f_src-f_dst)²), empty→0`
- `def has_sponsored_neighbor(collab_edge_index,creator_is_sponsored): result[dst[sponsored]]=True`
- `def consistency_penalty(exposure,has_sponsored_neighbor): exposure[~has].pow(2).mean()`

### `backend/app/routers/health.py:1`
- `@router.get("/health") def health_check:12` — `session.exec(text("SELECT 1")) → db_connected bool; return HealthResponse(status="ok")`

### `backend/app/routers/influencers.py:1`
- `def _extract_keywords(query):66` — `[w for w in lower.split if len>=3]`
- `def _keyword_overlap(keywords,texts):72` — `any(k in combined)` lower; empty keywords→False
- `def _has_preferred_platform(creator,platforms):93` — handles `{youtube:youtube_handle,instagram:instagram_handle,reddit:reddit_handles}`; any `handles[p]`
- `def _to_recommendation(...):104` — resolves live `spillover_info` (score, basis, hw=|conf_high-score|), fallback stored `score` or 0.5; `compute_fusion_score(spillover, sentiment if score else 0.5, creator_feat if score else 0.5, hw)`; `reach=max(subscriber,follower)`, `estimated_cost=reach*0.5`
- `@router.post("/recommendations") def get_recommendations:160` — `creators=select(Creator).limit(1000)` else mock; batch `spillover_map=get_spillover_batch(ids)`; for each: budget `estimated_cost>budget→skip`; platform hard `not _has_preferred_platform→skip`; region/demographic/product soft `if keywords and has_signal and not _keyword_overlap→skip`; fetch latest `FusionScore` per creator; `_to_recommendation`; sort `final_score desc`, slice `max_results`; `is_mock_data=using_mock_creators or any_score_missing`.

### `backend/app/routers/scores.py:1`
- `@router.post("/compute") def compute_score:24` — if `payload.spillover_score is None → sp=get_spillover(creator_id)` else `spillover=payload basis="placeholder" hw=None`; `compute_fusion_score(spillover,sentiment,creator_feat, hw)`; `record=FusionScore(... spillover_basis=basis ...)`; `add/commit/refresh`; returns `FusionScoreResponse`
- `@router.get("/{creator_id}") def get_latest_score:75` — `sp=get_spillover(creator_id)` live; `live_hw`; `record=select(FusionScore where creator_id).order_by(computed_at desc).first()`; if record → `compute_fusion_score(live_spillover, record.sentiment, record.creator_feature, hw)` with `computed_at=record.computed_at`; else on-the-fly `0.5,0.5` with `now UTC`; never 404.

### `backend/app/routers/feature_store.py:1`
- `@router.get("/creators") def get_creator_features:17` — `build_creator_features`
- `@router.get("/edges/collaborations") def get_collaboration_edges:22` — `build_collaboration_edges`
- `@router.get("/edges/sponsorships") def get_sponsorship_edges:27` — `build_sponsorship_edges`
- `@router.get("/edges/co-occurrence") def get_co_occurrence_edges:32` — `build_co_occurrence_edges`

### `backend/app/routers/alerts.py:1`
- `@router.post("") def create_alert:22` — `RiskAlert(**payload.model_dump()); add/commit/refresh; return AlertResponse`
- `@router.get("") def list_alerts:31` — `select(RiskAlert); if creator_id: where; if not include_resolved: where resolved==False; order_by created_at desc`

### `backend/app/routers/labeling.py:1`
- `@router.post("/run") def run_labeling:35` — default only `is_sponsored IS NULL`; `force=true` reprocesses all; YouTube `found,matches=detect_sponsorship(title,description)` → `is_sponsored=found`; Instagram same but `if has_paid_partnership_label: found=True matches+=["native:paid_partnership_label"]`; Reddit `title,body`; commit; return `LabelingRunResponse`.

### `backend/app/routers/ingestion.py:1`
- `def _upsert_by_pk(session, model, pk_field, payload):48` — `for item in payload: existing=session.get(model,pk); if existing: setattr + add else add(new); commit; return IngestionResponse`
- `@router.post("/creators") def ingest_creators:68` — upserts by `creator_id`
- `@router.post("/creators/related-accounts") def ingest_creator_related_accounts:90` — upserts by unique `(creator_id,platform,handle)`
- `@router.post("/youtube/channels") def ingest_youtube_channels:120` → `_upsert_by_pk(YouTubeChannel,"channel_id")`
- `@router.post("/youtube/videos") def ingest_youtube_videos:125` → `YouTubeVideo`
- `@router.post("/instagram/profiles") def ingest_instagram_profiles:130` → `InstagramProfile`
- `@router.post("/instagram/posts") def ingest_instagram_posts:135` → `InstagramPost`
- `@router.post("/reddit/profiles") def ingest_reddit_profiles:140` → `RedditProfile`
- `@router.post("/reddit/posts") def ingest_reddit_posts:145` → `RedditPost` (all 8 require `X-API-Key` if `API_KEY` set)

### `backend/migrations/0001_init_fusion_alerts.sql:1`
- `CREATE TABLE fusionscore:13` — `id serial PK, creator_id uuid NOT NULL, spillover_score double, sentiment_risk_score double, creator_feature_score double, final_score double, confidence_low double, confidence_high double, risk_adjustment double, computed_at timestamp NOT NULL` `IF NOT EXISTS`
- `CREATE TABLE riskalert:26` — `id serial PK, creator_id uuid NOT NULL, severity varchar, reason varchar, source varchar, created_at timestamp, resolved boolean` `IF NOT EXISTS`

### `backend/migrations/0002_add_alerts_propagated_from.sql:1`
- `ALTER TABLE riskalert ADD COLUMN propagated_from_creator_id uuid:14` — `IF NOT EXISTS`

### `backend/migrations/0003_add_fusion_spillover_basis.sql:1`
- `ALTER TABLE fusionscore ADD COLUMN spillover_basis varchar(12) NOT NULL DEFAULT 'placeholder':6` — P1.6 provenance `trained|inferred|placeholder|isolated`.

---

## Track D — Frontend+App

### `frontend/src/app/page.tsx:3`
- `export default function Home()` — static landing `<main>` with `h1` “Influencer-Brand Matching”, `<p>` ROI/spillover, CTA `<Link href="/brand-input">Start a new brand request</Link>`. Server component, no hooks, no API, no spillover/confidence.

### `frontend/src/app/layout.tsx:6`
- `const geistSans = Geist({ variable: "--font-geist-sans", subsets: ["latin"] })` + `geistMono = Geist_Mono({ variable: "--font-geist-mono"})`; `export const metadata: Metadata = { title: "Influencer-Brand Matching", description: "ROI/spillover-based influencer recommendation system" }`; `export default function RootLayout({ children }: LayoutProps<"/">)` — `<html lang="en">` with fonts, `<body min-h-full flex flex-col>` containing `<Nav />` + `{children}`. No spillover/confidence.

### `frontend/src/app/brand-input/page.tsx:12`
- `export default function BrandInputPage()` — `"use client"` form: Product/Category, Budget (INR), Target Region/Demographic via `Field`, error `<p>`, submit disabled `!productCategory||!budget||isSubmitting`; state `productCategory, budget, targetRegion, targetDemographic`, `isSubmitting`, `error`, `router: useRouter()`; API `postRecommendations({ product_category, budget:Number(budget), target_region?, target_demographic? })` → `sessionStorage.setItem("recommendationResult", JSON.stringify(response))` + `router.push("/dashboard")`; inner `async function handleSubmit(e: React.FormEvent): Promise<void>` prevents default, clears error, awaits, catches `"Couldn't reach recommendation API. Is Track C backend running at ...?"`.
- `function Field({ label, placeholder, value, onChange, type="text", required=false }: {...})` — `<label><span>label</span><input type={type} value={value} onChange={e=>onChange(e.target.value)} placeholder className="rounded-md border..."/></label>`. No spillover/confidence; produces request that later returns `spillover_basis` + `confidence_low/high`.

### `frontend/src/app/dashboard/page.tsx:15`
- `export default function DashboardPage()` — `"use client"` dashboard: `useStoredRecommendationResult()`; `useEffect` `getAlerts()` → `Map<string,AlertResponse[]>`; empty-state link to `/brand-input`; header `Results for "query.product_category", budget ₹…`, amber banner if `is_mock_data`, `<ul>` of `result.results.map` cards; state `result, alertsByCreator`; API `getAlerts()` supplementary; core spillover usage `basis = (influencer.spillover_basis ?? "placeholder") as SpilloverBasis`; `<SpilloverBadge basis={basis} />`, `basis: {basis}`, isolated note; `spilloverRaw = score_breakdown.spillover_score` `isOutOfRange = <0||>1` warning; `confidence_low/high` as `confidence {low.toFixed(0)}–{high.toFixed(0)}`; sublabels `trained→"±13pts wide (N=10)"`, `inferred→"±21pts wide"`, `placeholder/isolated→"±10pts"`.
- `function ScorePart({ label, value, sublabel }: { label:string; value:string; sublabel?:string })` — `rounded-md bg-zinc-50 px-3 py-2` with label/value/sublabel for 3-column grid Spillover/Sentiment-Risk placeholder 0.5/Feature placeholder 0.5.

### `frontend/src/app/explainability/page.tsx:15`
- `export default function ExplainabilityPage()` — `"use client"` explainability: same `useStoredRecommendationResult()`; maps `result.results` to `<li>` cards showing `<SpilloverBadge basis={basis}>`, isolated note, mono formula `{final_score.toFixed(1)} = ({weight_spillover}×{spillover_score})+...×100 {+ derivedRiskAdjustment}`, out-of-range warning, 3× `Contribution`, confidence paragraph, basis description, fixed footer placeholder note about network-graph/Granger causality (Track B weeks 11-13); derived `spilloverContribution = weight_spillover*spillover_score*100` etc, `weightedSum`, `derivedRiskAdjustment = final_score - weightedSum`.
- `function Contribution({ label, points, hint }: { label:string; points:number; hint?:string })` — `rounded-md bg-zinc-50` with `label`, `points.toFixed(1) pts`, optional `hint`. Used for Spillover, Sentiment/Risk, Creator Features contributions.

### `frontend/src/app/monitoring/page.tsx:11`
- `function resolveName(id: string, namesById: Map<string,string>): string` — `return namesById.get(id) ?? id`.
- `export default function MonitoringPage()` — `"use client"` alerts feed: `useEffect` fetches `getAlerts()` → `alerts: AlertResponse[]|null` and `getCreators()` → `Map<creator_id,name>`; loading/empty/error/`<ul>` cards with `SeverityBadge`, `toLocaleString()` date, `creator: resolveName(...)`, `reason`, `source`, optional `propagated from collaborator: resolveName(propagated_from_creator_id)`. State `alerts, error, namesById`; API `getAlerts()` + `getCreators()` (`GET /feature-store/creators`); no spillover/confidence.

### `frontend/src/components/Nav.tsx:3`
- `const links = [{href:"/brand-input",label:"Brand Input"}, {href:"/dashboard",label:"Dashboard"}, {href:"/monitoring",label:"Monitoring"}, {href:"/explainability",label:"Explainability"}]`; `export default function Nav()` — `<header border-b>` with `<nav mx-auto max-w-5xl>` home `<Link href="/" font-semibold>` “Influencer-Brand Matching” + `links.map`.

### `frontend/src/components/SeverityBadge.tsx:3`
- `const styles: Record<AlertSeverity,string> = { low:"bg-zinc-100...", medium:"bg-amber-100...", high:"bg-red-100..." }`; `export default function SeverityBadge({ severity }: { severity: AlertSeverity })` — `<span rounded-full px-2 py-1 text-xs font-medium ${styles[severity]}>` `{severity} severity`.

### `frontend/src/components/SpilloverBadge.tsx:6`
- `const BASIS_META: Record<SpilloverBasis,{label:string;className:string;short:string}>` — `trained→"Trained — N=10" emerald`, `inferred→"Inferred — wide CI" violet`, `placeholder→"Placeholder" zinc`, `isolated→"Placeholder — no graph signal" zinc dashed`
- `const TOOLTIP_COPY: Record<SpilloverBasis,string>` — long-form provenance: `trained` (GAIL N=10 df=8 t=2.306 mse=1.84 → hw≈3.28 → CI hw·100·w1 w1=0.4 → ±13pts clamped), `inferred` (hw≈5.25 1.6× → ±21pts), `placeholder` (hw0.25→±10pts), `isolated` (degree 0 → IsolatedCreatorError→placeholder 0.5). References `backend/app/fusion.py:57`, `API_CONTRACTS.md P1.6`, `CAPSTONE_NEXT_STEPS:795/822`.
- `export function basisLabel(basis: SpilloverBasis): string` — `return BASIS_META[basis]?.label ?? basis`
- `export default function SpilloverBadge({ basis, compact=false }: { basis:SpilloverBasis; compact?:boolean })` — `"use client"` interactive badge: `useState(open)`, `useId()`, `useRef<HTMLButtonElement>`; `<button aria-describedby aria-expanded onMouseEnter/Leave onFocus/Blur onClick toggle>` with `meta.className` + `?` circle; conditional `{open && <span role="tooltip" absolute ...>` showing `meta.label: copy` + sentiment note. No API.
- `export function isolatedNote(): string` — `return "no graph signal — degree 0 on collaborates_with + co_occurs_with (IsolatedCreatorError → placeholder 0.5, never inferred)"`

### `frontend/src/lib/api.ts:8`
- `const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000"`; `export async function postRecommendations(body: BrandRecommendationRequest): Promise<BrandRecommendationResponse>` — `fetch(${API_BASE_URL}/recommendations, {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(body)})`; throws if `!res.ok`; returns `BrandRecommendationResponse` (carries `spillover_basis` + `confidence_low/high`, comment notes honest small-N hw margins). `export async function getAlerts(): Promise<AlertResponse[]>` — `fetch(${API_BASE_URL}/alerts)`; `export async function getCreators(): Promise<CreatorSummary[]>` — `fetch(${API_BASE_URL}/feature-store/creators)`.

### `frontend/src/lib/useStoredRecommendationResult.ts:9`
- `export function useStoredRecommendationResult(): BrandRecommendationResponse | null` — `useSyncExternalStore(()=>()=>{}, ()=>sessionStorage.getItem("recommendationResult"), ()=>null)` hydration-safe browser-only read; parses JSON → `BrandRecommendationResponse`; patches stale cache `if (!r.spillover_basis) r.spillover_basis="placeholder"`; catches parse error → `null`.

### `frontend/src/types/index.ts:5`
- `export type SpilloverBasis = "trained" | "inferred" | "placeholder" | "isolated"` — provenance discriminator mirrored from `backend/app/schemas.py:65ec502`
- `export interface ScoreBreakdown` — `spillover_score (0-1 but live >>1 e.g. 21.6), sentiment_risk_score placeholder 0.5 per CAPSTONE_NEXT_STEPS:822, creator_feature_score placeholder 0.5, weight_spillover/sentiment_risk/creator_feature`.
- `export interface BrandRecommendationRequest` — `{ product_category:string; budget:number INR >0 finite; target_region?:string; target_demographic?:string; platform_preference?:("youtube"|"instagram"|"reddit")[]; max_results?:number }`
- `export interface InfluencerRecommendation` — `{ creator_id:string(uuid); name:string; category:string|null; youtube_handle:string|null; instagram_handle:string|null; reddit_handles:string[]; final_score:number(0-100); confidence_low:number; confidence_high:number; spillover_basis?:SpilloverBasis fallback ??"placeholder"; estimated_reach:number|null; estimated_cost:number|null; score_breakdown:ScoreBreakdown }` — `confidence_low/high` derived `margin=hw*100*w1` clamped [0,100].
- `export interface BrandRecommendationResponse` — `{ query:BrandRecommendationRequest; results:InfluencerRecommendation[]; is_mock_data:boolean }`
- `export interface CreatorSummary` — `{creator_id:string(uuid); name:string}` for monitoring.
- `export type AlertSeverity = "low" | "medium" | "high"`; `export interface AlertResponse` — `{id:number; creator_id:string(uuid); severity:AlertSeverity; reason:string; source:string; propagated_from_creator_id:string|null; created_at:string; resolved:boolean}`

### `frontend/next.config.ts:3`
- `const nextConfig: NextConfig = { output: "standalone" }` + `export default nextConfig` — enables standalone output for Docker.

### `frontend/package.json:1`
- `name: "frontend" version:"0.1.0" private:true`; scripts `dev: next dev`, `build: next build`, `start: next start`, `lint: eslint`; dependencies `next 16.3.0`, `react 19.2.8`, `react-dom 19.2.8`; devDeps `@tailwindcss/postcss ^4`, `@types/node ^20`, `@types/react ^19`, `tailwindcss ^4`, `typescript ^5`.

### `frontend/Dockerfile:1`
- `FROM node:20-alpine AS deps` — `WORKDIR /app` + `COPY package.json package-lock.json` + `RUN npm ci`
- `FROM node:20-alpine AS builder` — `COPY --from=deps node_modules`, `COPY . .`, `RUN npm run build` (→ `.next/standalone`)
- `FROM node:20-alpine AS runner` — `ENV NODE_ENV=production`, `addgroup/adduser nextjs:nodejs 1001`, `COPY --from=builder /app/public`, `COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./`, `COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static`, `USER nextjs`, `EXPOSE 3000`, `ENV PORT=3000 HOSTNAME=0.0.0.0`, `CMD ["node","server.js"]`.

---

## Cross-reference: honest small-N story

- **N=10 effective** `ml/inference.py:109` / `scripts/train_prod_model.py:492` — 54 rows → 10 distinct creator-nodes (Kohli 16 rows → 1). LOO MSE 67.19 vs 67.36 baseline, ex-Kohli ~14% win, propensity 1.000 saturation fixed via z-score `compute_feature_scaler` (mean 0.61 after). Thesis caveat verbatim.
- **Confidence** `backend/app/gail/inference.py:109` `base_hw = max(t*residual_std*sqrt(1+1/N),0.15)` `t=_t_critical(df)`, `inferred_hw = max(base*1.6,0.25)` → `±13pts` trained `hw≈3.28`, `±21pts` inferred `hw≈5.25`, `±10pts` placeholder via `fusion.py:57` `margin=hw*100*w1` clamped.
- **Sentiment** `CAPSTONE_NEXT_STEPS:822` — `w2=0.5` placeholder, `reputation_score` always None, Temporal branch 0% (134k comments exist but not aggregated). `SpilloverBadge.tsx:36` tooltip documents this so UI never presents placeholder as validated.
- **Demo archetypes** `backend/app/routers/scores.py:75` + `frontend/src/app/dashboard/page.tsx:15`: `c4b20 Virat trained 21.61→100 [0-100]` (emerald), `89972 AB inferred 1.19→77 [0-100]` (violet), `78e48 _bungy isolated 0.5→50 [40-60]` (zinc dashed, degree 0 → `IsolatedCreatorError` → placeholder, never inferred).

---

*End of `functions.md` — every file on `review-1` `123f489` documented. For manual run steps see `manual.md`.*
