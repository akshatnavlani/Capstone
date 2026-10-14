"""Collect Reddit discussion about our verified fitness creators and about fitness brands.

    python reddit_collect.py --dry-run                              # show the plan, call nothing
    python reddit_collect.py --creators 10 --brands 6               # small pilot
    python reddit_collect.py --subs indianfitness Fitness_India     # the default subreddits

WHY a new collector (the old RedditWorker in orchestrator.py is left as it was):
  * its name match produced about 24% wrong creator links (S8 audit): single first names and common words matched.
    Here a creator matches a post only when the post names one of THEIR aliases (full name, nickname in brackets, or
    a handle of 6+ characters), never a lone first name;
  * `opencli reddit read` returns comments without ids or times, so comment times were 0 of 55,194. Here each thread
    is read from the page's own JSON, which carries every comment's id, exact time (created_utc), author, score and
    parent;
  * it also searches the fitness BRANDS (MuscleBlaze, Wellcore ...) so audience opinion can be tied to brands.

Request budget: the search and thread loads go through the signed-in Chrome (OpenCLI). It waits GAP_SECONDS between
requests, stops at the first sign of a block (HTTP 429, "rate limit") or after two failures in a row, and only
reads: no votes, comments or follows.
"""

import argparse
import json
import re
import time
from datetime import datetime, timezone

import psycopg2
from psycopg2.extras import execute_values

from known_brands import match_known_brands
from orchestrator import RateLimiter, get_connection, log, run_opencli

DEFAULT_SUBS = ["indianfitness", "Fitness_India"]
GAP_SECONDS = 12.0
COOLDOWN_SECONDS = 300   # one pause when Reddit starts refusing, then one retry, then stop (everything done so far is saved)
MAX_CONSECUTIVE_FAILURES = 2
BRAND_QUERIES = ["MuscleBlaze", "Wellcore", "Nutrabay", "NaturalTein", "Avvatar", "FuelOne", "Boldfit", "HealthKart", "Fast and Up",
                 "Wellversed", "AsItIs", "Black Beast", "GNC", "Myprotein", "QNT", "Ripped Up Nutrition", "Nakpro", "Gayor",
                 "BigMuscles", "Red Skull", "TrueForma", "Optimum Nutrition"]
# search word -> the brand's name in the `brands` table, where they differ
BRAND_DB_NAME = {"Fast and Up": "Fast&Up", "AsItIs": "AsItIs Nutrition", "Black Beast": "Black Beast Nutrition", "Gayor": "Gayor Essentials",
                 "BigMuscles": "BigMuscles Nutrition", "Red Skull": "Red Skull Nutrition", "Optimum Nutrition": "optimumnutri"}
_STOP = {"fitness", "gym", "official", "india", "indian", "the", "vlogs", "vlog", "coach", "fit", "health", "channel"}

# Page script: the whole thread as JSON (post + every comment with id, time, author, score, body, parent).
_THREAD_JS = ("(async()=>{const r=await fetch(location.pathname.replace(/[/]+$/,'')+'.json?limit=1000'+String.fromCharCode(38)+'raw_json=1');"
              "if(!r.ok)return JSON.stringify({status:r.status});const j=await r.json();const out=[];"
              "const walk=(ch)=>{for(const x of ch){if(x.kind==='t1'){const d=x.data;"
              "out.push({id:d.id,t:d.created_utc,a:d.author,s:d.score,b:d.body,p:d.parent_id});"
              "if(d.replies){if(d.replies.data){walk(d.replies.data.children)}}}}};walk(j[1].data.children);"
              "const p=j[0].data.children[0].data;return JSON.stringify({post:{id:p.id,t:p.created_utc,sub:p.subreddit,"
              "a:p.author,title:p.title,body:p.selftext,s:p.score,n:p.num_comments},comments:out})})()")
# Windows runs `opencli` through cmd.exe: a double quote or an ampersand inside this argument would split the command,
# so the script uses single quotes only and builds the '&' with String.fromCharCode(38).


def aliases(display_name: str, yt_handle: str | None, ig_handle: str | None) -> set[str]:
    """Lowercase strings that, found in a post, identify this creator. A lone first name never qualifies."""
    out: set[str] = set()
    main = re.sub(r"\(.*?\)", " ", display_name or "").strip()
    inner = re.findall(r"\((.*?)\)", display_name or "")
    for cand in [main, *inner]:
        cand = re.sub(r"\s+", " ", cand).strip().lower()
        tokens = [t for t in re.split(r"\s+", cand) if t]
        if len(tokens) >= 2 and not all(t in _STOP for t in tokens):
            out.add(cand)
        elif len(tokens) == 1 and len(cand) >= 8 and cand not in _STOP:
            out.add(cand)
    for h in (yt_handle, ig_handle):
        h = (h or "").lower().lstrip("@")
        if len(h) >= 6 and h not in _STOP:
            out.add(h)
    return out


def matches(text: str, creator_aliases: set[str]) -> bool:
    """True when the text names the creator by one of their aliases (whole-word, case-insensitive)."""
    low = (text or "").lower()
    return any(re.search(r"(?<![a-z0-9])" + re.escape(a) + r"(?![a-z0-9])", low) for a in creator_aliases)


def clean_sub(raw: str | None) -> str | None:
    """'r/Fitness_India' -> 'Fitness_India'; user profiles ('u/...') are not subreddits."""
    raw = (raw or "").strip()
    if raw.lower().startswith("u/"):
        return None
    return raw[2:] if raw.lower().startswith("r/") else raw or None


def parse_thread(raw) -> dict | None:
    """The _THREAD_JS output as {'post': {...}, 'comments': [...]} with UTC datetimes, or None."""
    data = raw
    if isinstance(raw, str):
        try:
            data = json.loads(raw)
        except ValueError:
            return None
    if not isinstance(data, dict) or "post" not in data:
        return None

    def when(t):
        try:
            return datetime.fromtimestamp(float(t), tz=timezone.utc).replace(tzinfo=None)
        except (TypeError, ValueError):
            return None
    p = data["post"]
    comments = [{"id": c["id"], "at": when(c.get("t")), "author": c.get("a"), "score": c.get("s"), "body": c.get("b")}
                for c in data.get("comments", []) if c.get("id")]
    return {"post": {**p, "at": when(p.get("t"))}, "comments": comments}


def brands_named(text: str) -> set[str]:
    """Names of the known brands a text mentions by their full name, handle or known spelling (whole words, not a first word)."""
    return {m.name for m in match_known_brands(text)}


def pick_brand(title: str, body: str, labels: set[str] | None = None) -> str | None:
    """Which known brand a thread is about: the one named in its title, else one named in its text. None when no brand
    is really named (a search for 'Red Skull' also returns posts that merely say 'red')."""
    in_title, in_body = brands_named(title or ""), brands_named(body or "")
    for group in (in_title, in_body):
        pool = sorted(group & labels) if labels else sorted(group)
        if pool:
            return pool[0]
    return None


def looks_blocked(text: str) -> bool:
    """HTTP 429, rate-limit wording, or the browser's 'Failed to fetch' (Reddit refuses by dropping the request)."""
    low = (text or "").lower()
    return "429" in low or "rate limit" in low or "too many requests" in low or "failed to fetch" in low


def save_search_post(cur, p: dict, creators: set, brand_id) -> None:
    """Save a post found by a search (no comments yet): its author, the post row and the creator links."""
    ts = p.get("created_utc")
    at = datetime.fromtimestamp(float(ts), tz=timezone.utc).replace(tzinfo=None) if ts else None
    author = p.get("author")
    if author:
        cur.execute("insert into reddit_profiles (username) values (%s) on conflict do nothing", (author,))
    first = sorted(creators, key=str)[0] if creators else None
    cur.execute("""insert into reddit_posts (post_id, subreddit, creator_id, author_username, title, body, posted_at, score, num_comments, brand_id)
                   values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                   on conflict (post_id) do update set score=excluded.score, num_comments=excluded.num_comments, fetched_at=now(),
                       creator_id=coalesce(reddit_posts.creator_id, excluded.creator_id), brand_id=coalesce(reddit_posts.brand_id, excluded.brand_id)""",
                (p["id"], clean_sub(p.get("subreddit")), first, author, p.get("title"), p.get("selftext"), at, p.get("score"), p.get("comments"), brand_id))
    for c in creators:
        cur.execute("insert into reddit_post_creators (post_id, creator_id) values (%s,%s) on conflict do nothing", (p["id"], c))


def save_thread(conn, p: dict, comments: list) -> None:
    """Save one thread's comments: authors first (foreign keys), then every comment with its exact time."""
    with conn.cursor() as cur:
        names = {x for x in [p.get("a")] + [c["author"] for c in comments] if x}
        if names:
            execute_values(cur, "insert into reddit_profiles (username) values %s on conflict do nothing", [(n,) for n in names])
        cur.execute("update reddit_posts set score=%s, num_comments=%s, body=coalesce(%s, body), fetched_at=now() where post_id=%s",
                    (p.get("s"), p.get("n"), p.get("body"), p["id"]))
        if comments:
            execute_values(cur, """insert into reddit_comments (comment_id, post_id, author_username, body, posted_at, score) values %s
                                   on conflict (comment_id) do update set score=excluded.score,
                                       posted_at=coalesce(excluded.posted_at, reddit_comments.posted_at)""",
                           [(c["id"], p["id"], c["author"], c["body"], c["at"], c["score"]) for c in comments])
    conn.commit()


def safe_query(label: str) -> str:
    """Windows runs `opencli` through cmd.exe, where & | < > ^ % and quotes split or change the command: use spaces instead."""
    return re.sub(r"\s+", " ", re.sub(r"[&|<>^%\"]", " ", label)).strip()


def search(limiter, label: str, sub: str, per_query: int):
    """One Reddit search. When Reddit refuses, wait COOLDOWN_SECONDS once and retry; a second refusal raises."""
    for attempt in range(2):
        limiter.wait()
        try:
            return run_opencli("reddit", "search", safe_query(label), "--subreddit", sub, "--sort", "new", "--limit", str(per_query), "-f", "yaml", timeout=90)
        except RuntimeError as e:
            msg = str(e)[-200:].replace("\n", " ")
            if attempt == 0:
                log.warning("search %r in r/%s refused (%s); waiting %d s once", label, sub, msg, COOLDOWN_SECONDS)
                time.sleep(COOLDOWN_SECONDS)
                continue
            raise


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--subs", nargs="+", default=DEFAULT_SUBS)
    ap.add_argument("--creators", type=int, default=0, help="how many creators to search (0 = none)")
    ap.add_argument("--brands", type=int, default=0, help="how many brand queries to run (0 = none)")
    ap.add_argument("--per-query", type=int, default=25, help="newest results per search")
    ap.add_argument("--max-threads", type=int, default=60, help="threads to read in full per run")
    ap.add_argument("--skip-searches", action="store_true", help="only read threads of posts already saved")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute("""select v.creator_id, v.display_name, v.yt_handle, v.ig_handle from creator_verification v
                       where v.link_level in ('confirmed','probable') and v.creator_id is not null and v.content_type <> 'brand_like'
                       order by (v.sponsor_group = 'A') desc, v.ig_followers desc nulls last""")
        creators = cur.fetchall()
        cur.execute("select lower(name), brand_id from brands"); brand_ids = dict(cur.fetchall())
        cur.execute("select kind, query, subreddit from reddit_search_log where searched_at > now() - interval '7 days'")
        done = set(cur.fetchall())
    alias_of = {cid: aliases(n, y, i) for cid, n, y, i in creators}
    todo_creators = [(cid, n) for cid, n, _y, _i in creators if alias_of[cid]][:args.creators]
    queries = [("creator", cid, n) for cid, n in todo_creators] + [("brand", None, b) for b in BRAND_QUERIES[:args.brands]]
    pending = [(k, c, l, sub) for k, c, l in queries for sub in args.subs if (k, l, sub) not in done]
    log.info("plan: %d searches (%d already done in the last 7 days), then up to %d threads", len(pending), len(queries) * len(args.subs) - len(pending), args.max_threads)
    if args.dry_run:
        log.info("[DRY RUN] nothing was called")
        return

    limiter = RateLimiter(GAP_SECONDS)
    try:
        if not args.skip_searches:
            for kind, cid, label, sub in pending:
                posts = search(limiter, label, sub, args.per_query)
                kept = 0
                with conn.cursor() as cur:
                    for p in posts if isinstance(posts, list) else []:
                        text = f"{p.get('title', '')} {p.get('selftext', '')}"
                        who = {c for c, a in alias_of.items() if matches(text, a)}
                        if kind == "creator" and cid not in who:
                            continue
                        brand_id = None
                        if kind == "brand":
                            db_name = BRAND_DB_NAME.get(label, label)
                            if db_name not in brands_named(text):
                                continue
                            brand_id = brand_ids.get(db_name.lower())
                        if not clean_sub(p.get("subreddit")):
                            continue
                        save_search_post(cur, p, who, brand_id)
                        kept += 1
                    cur.execute("insert into reddit_search_log (kind, query, subreddit, results) values (%s,%s,%s,%s) on conflict (kind, query, subreddit) do update set "
                                "results=excluded.results, searched_at=now()", (kind, label, sub, kept))
                conn.commit()
                log.info("search %-28s r/%-14s -> %d posts kept", label[:28], sub, kept)

        # which brand a post is about: the one in its title, else in its text
        with conn.cursor() as cur:
            cur.execute("select post_id, title, body from reddit_posts where brand_id is not null and fetched_at > now() - interval '1 day'")
            for pid, title, body in cur.fetchall():
                pick = pick_brand(title or "", body or "")
                cur.execute("update reddit_posts set brand_id=%s where post_id=%s", (brand_ids.get(pick.lower()) if pick else None, pid))
        conn.commit()

        with conn.cursor() as cur:
            cur.execute("""select p.post_id, p.num_comments from reddit_posts p
                           where p.subreddit = any(%s) and coalesce(p.num_comments, 0) > 0 and (p.brand_id is not null or exists (select 1 from reddit_post_creators rc where rc.post_id = p.post_id))
                             and not exists (select 1 from reddit_comments c where c.post_id = p.post_id)
                           order by p.num_comments desc limit %s""", (args.subs, args.max_threads))
            todo = cur.fetchall()
        log.info("%d saved posts have no comments yet; reading up to %d", len(todo), args.max_threads)
        for pid, _n in todo:
            session = f"rd_{pid}"
            limiter.wait()
            try:
                run_opencli("browser", session, "open", f"https://www.reddit.com/comments/{pid}/")
                run_opencli("browser", session, "wait", "time", "3")
                thread = parse_thread(run_opencli("browser", session, "eval", _THREAD_JS))
            except RuntimeError as e:
                log.warning("thread %s failed: %s", pid, str(e)[-160:].replace("\n", " "))
                if looks_blocked(str(e)):
                    raise
                continue
            finally:
                try:
                    run_opencli("browser", session, "close", timeout=20)
                except RuntimeError:
                    pass
            if not thread:
                continue
            try:
                save_thread(conn, thread["post"], thread["comments"])
            except psycopg2.Error as e:
                conn.rollback()
                log.warning("could not save thread %s: %s", pid, str(e)[:160].replace("\n", " "))
                continue
            log.info("thread %s: %d comments with times", pid, len(thread["comments"]))
    except RuntimeError as e:
        log.error("stopping the whole run (everything so far is saved; run again to resume): %s", str(e)[-220:].replace("\n", " "))
    log.info("done")


if __name__ == "__main__":
    main()
