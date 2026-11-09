"""Fetch each creator's public YouTube channel photo URL and save them to models/creator_photos.json (1 Nov 2026).

One YouTube Data API call (1 quota unit) per 50 channels, so the whole set costs about 9 units. Only the photo's web address is saved, not the picture; the app
shows it from YouTube and falls back to initials when there is no photo or the link fails. Creators with no YouTube channel simply get no entry.

    python scripts/fetch_creator_photos.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts" / "ingestion"))
from orchestrator import get_connection, youtube_api_get  # noqa: E402

conn = get_connection()
cur = conn.cursor()
cur.execute("select creator_id::text, channel_id from youtube_channels where creator_id is not null and channel_id is not null")
rows = cur.fetchall()
conn.close()
by_channel = {}
for creator_id, channel_id in rows:
    by_channel.setdefault(channel_id, creator_id)
channels = list(by_channel)
print(f"{len(channels)} channels to look up")

photos = {}
for i in range(0, len(channels), 50):
    batch = channels[i : i + 50]
    resp = youtube_api_get("channels", part="snippet", id=",".join(batch), maxResults=50)
    for item in resp.get("items", []):
        thumbs = (item.get("snippet") or {}).get("thumbnails") or {}
        pick = thumbs.get("medium") or thumbs.get("default") or thumbs.get("high")
        if pick and pick.get("url"):
            photos[by_channel[item["id"]]] = pick["url"]
    print(f"  looked up {min(i + 50, len(channels))} of {len(channels)}")

out = ROOT / "models" / "creator_photos.json"
out.write_text(json.dumps({"source": "YouTube Data API channels.list snippet.thumbnails", "count": len(photos), "photos": photos}, indent=1), encoding="utf-8")
print(f"saved {len(photos)} photo links to {out}")
