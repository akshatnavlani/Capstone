"""Exact posting time of an Instagram post, decoded from its shortcode. No network.

A shortcode is the media id written in base64 over ALPHABET, and the id's high bits are a
millisecond timestamp counted from Instagram's own epoch:

    posted_at = (media_id >> 23) + 1314220021721 ms   (UTC)

The shift and epoch were fitted and checked against posts dated from an independent source in
backfill_dates_from_shortcode.py (99.4% within 72h; the residual gap there is only because those
sources are date-only). The collector now writes this value for every post it sees, so a post is
never stored with a bare date when its real time is known.
"""

import datetime

ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
INSTAGRAM_EPOCH_MS = 1314220021721
SHIFT = 23


def decode(shortcode: str) -> datetime.datetime | None:
    """UTC datetime encoded in the shortcode, or None if it is not a valid shortcode."""
    if not shortcode:
        return None
    media_id = 0
    for ch in shortcode:
        if ch not in ALPHABET:
            return None
        media_id = media_id * 64 + ALPHABET.index(ch)
    try:
        return datetime.datetime.fromtimestamp(
            ((media_id >> SHIFT) + INSTAGRAM_EPOCH_MS) / 1000, datetime.timezone.utc)
    except (ValueError, OSError, OverflowError):
        return None


def parse_listing_date(raw: str | None) -> datetime.datetime | None:
    """"M/D/YYYY" (the format the listing and og:description give) as midnight UTC, else None."""
    try:
        return datetime.datetime.strptime(raw, "%m/%d/%Y").replace(tzinfo=datetime.timezone.utc)
    except (ValueError, TypeError):
        return None


def posted_at_for(post_id: str, listing_date: str | None) -> datetime.datetime | None:
    """Best known posting time: the exact decoded instant, else the listing's date at midnight."""
    return decode(post_id) or parse_listing_date(listing_date)
