"""Creator-to-creator collaboration pairs from creator_related_accounts.

Same handle resolution as scripts/train_prod_model.py load_collab_edges
(case-insensitive, '@', 'u/', 'r/' prefixes stripped, ambiguous handles
dropped), returned as plain id pairs for scripts that need links without
building a graph.
"""

from __future__ import annotations

from collections import defaultdict


def _norm(h: str) -> str:
    if not h:
        return ""
    h = h.strip().lower()
    for p in ("@", "u/", "r/"):
        if h.startswith(p):
            h = h[len(p):]
    return h


def collaboration_pairs(cur) -> set[tuple[str, str]]:
    """Unordered (a, b) creator-id pairs, a < b, linked as frequent collaborators."""
    cur.execute("select creator_id::text, youtube_handle, instagram_handle, reddit_handles from creators")
    owners = {"youtube": defaultdict(set), "instagram": defaultdict(set), "reddit": defaultdict(set)}
    for cid, yt, ig, rh in cur.fetchall():
        if yt:
            owners["youtube"][_norm(yt)].add(cid)
        if ig:
            owners["instagram"][_norm(ig)].add(cid)
        for h in rh or []:
            owners["reddit"][_norm(h)].add(cid)
    handle_map = {p: {h: next(iter(s)) for h, s in d.items() if len(s) == 1} for p, d in owners.items()}
    cur.execute("select creator_id::text, platform, handle from creator_related_accounts "
                "where relation_type='frequent_collaborator'")
    pairs = set()
    for cid, platform, handle in cur.fetchall():
        target = handle_map.get(platform, {}).get(_norm(handle or ""))
        if target and target != cid:
            pairs.add(tuple(sorted((str(cid), str(target)))))
    return pairs


def india_links(creator_ids: set[str], indian_people: set[str], collab: set[tuple[str, str]],
                creator_names: dict[str, str] | None = None) -> dict[str, str]:
    """For each creator in `creator_ids`, the Indian people they collaborate with,
    or no entry if none.

    Rule set by the user (28 Oct): only collaborations with Indian PEOPLE count
    (creators, athletes, celebrities). A team or league account listing a player
    is not a connection, and brand deals do not count (global brands such as Nike
    also sponsor Indian creators, so they cannot show Indian-market reach).
    """
    partners: dict[str, set[str]] = defaultdict(set)
    for a, b in collab:
        partners[a].add(b)
        partners[b].add(a)
    out = {}
    for c in creator_ids:
        linked = partners.get(c, set()) & indian_people
        if linked:
            names = sorted((creator_names or {}).get(x, x) for x in linked)
            out[c] = "collaborates with: " + ", ".join(names[:5])
    return out
