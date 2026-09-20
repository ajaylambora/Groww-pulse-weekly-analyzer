"""Pull recent reviews from the two public store feeds.

Both sources are open endpoints -- nothing here logs in or scrapes a gated page.
Author names are never read, so they cannot leak downstream.

Each source pages backwards until it passes the look-back cutoff, so the amount
of work scales with the window you ask for rather than a guessed row count.
"""
import hashlib
from datetime import datetime, timedelta, timezone

import pandas as pd
import requests

from . import config
from .pii import scrub

COLUMNS = ["review_id", "source", "date", "week", "rating", "title", "text"]
_UA = {"User-Agent": "Mozilla/5.0 (compatible; groww-review-pulse/1.0)"}


def _row_id(source, date, text):
    seed = f"{source}|{date}|{text}".encode("utf-8", "ignore")
    return hashlib.sha1(seed).hexdigest()[:12]


def _iso_week(dt):
    year, week, _ = dt.isocalendar()
    return f"{year}-W{week:02d}"


def _cutoff(weeks_back):
    return datetime.utcnow() - timedelta(weeks=weeks_back)


def fetch_apple(cutoff, app_id=None, country=None, max_pages=None):
    """Apple's public customer-review RSS feed. It only exposes ~500 reviews."""
    app_id = app_id or config.APPLE_APP_ID
    country = country or config.COUNTRY
    max_pages = max_pages or config.APPLE_MAX_PAGES
    rows = []
    for page in range(1, max_pages + 1):
        url = (f"https://itunes.apple.com/{country}/rss/customerreviews/"
               f"page={page}/id={app_id}/sortBy=mostRecent/json")
        try:
            payload = requests.get(url, headers=_UA, timeout=30).json()
        except Exception:
            break
        entries = payload.get("feed", {}).get("entry", [])
        if isinstance(entries, dict):
            entries = [entries]
        # The first entry of page 1 is app metadata, not a review.
        entries = [e for e in entries if "im:rating" in e]
        if not entries:
            break
        for e in entries:
            when = datetime.fromisoformat(e["updated"]["label"]).astimezone(timezone.utc)
            rows.append({
                "source": "App Store",
                "date": when.replace(tzinfo=None),
                "rating": int(e["im:rating"]["label"]),
                "title": e.get("title", {}).get("label", ""),
                "text": e.get("content", {}).get("label", ""),
            })
        if rows[-1]["date"] < cutoff:      # feed is newest-first, so we are done
            break
    return rows


def fetch_play(cutoff, package=None, country=None, lang=None, hard_cap=None):
    """Google Play's public review listing, paged newest-first until the cutoff."""
    package = package or config.PLAY_PACKAGE
    country = country or config.COUNTRY
    lang = lang or config.LANG
    hard_cap = hard_cap or config.PLAY_HARD_CAP
    from google_play_scraper import Sort, reviews

    rows, token = [], None
    while len(rows) < hard_cap:
        try:
            batch, token = reviews(package, lang=lang, country=country, sort=Sort.NEWEST,
                                   count=200, continuation_token=token)
        except Exception:
            break
        if not batch:
            break
        for r in batch:
            rows.append({
                "source": "Play Store",
                "date": r["at"],
                "rating": int(r["score"]),
                "title": "",
                "text": r.get("content") or "",
            })
        if token is None or rows[-1]["date"] < cutoff:
            break
    return rows


def fetch_reviews(weeks_back=None, sources=("apple", "play")):
    """Fetch, scrub, de-duplicate and window the reviews. Returns a DataFrame."""
    weeks_back = weeks_back or config.WEEKS_BACK
    cutoff = _cutoff(weeks_back)

    raw = []
    if "apple" in sources:
        raw += fetch_apple(cutoff)
    if "play" in sources:
        raw += fetch_play(cutoff)
    if not raw:
        return pd.DataFrame(columns=COLUMNS)

    rows = []
    for r in raw:
        when = pd.to_datetime(r["date"]).to_pydatetime().replace(tzinfo=None)
        if when < cutoff:
            continue
        text = scrub(r["text"])
        if not text:
            continue
        rows.append({
            "review_id": _row_id(r["source"], when.date(), text),
            "source": r["source"],
            "date": when.date().isoformat(),
            "week": _iso_week(when),
            "rating": r["rating"],
            "title": scrub(r["title"]),
            "text": text,
        })

    df = pd.DataFrame(rows, columns=COLUMNS)
    return df.drop_duplicates("review_id").sort_values("date", ascending=False).reset_index(drop=True)
