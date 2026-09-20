"""Group reviews into the five fixed themes from config.

Deliberately keyword-scored rather than model-clustered: the buckets have to
mean the same thing every week for the trend line to be readable, and a rule
you can print is a rule the product team can argue with.
"""
import re

import pandas as pd

from . import config

UNTHEMED = ""


def _compile(theme):
    phrases = re.compile("|".join(re.escape(p) for p in theme["phrases"]))
    words = re.compile(r"\b(?:" + "|".join(re.escape(w) for w in theme["words"]) + r")\b")
    return phrases, words


_PATTERNS = {key: _compile(t) for key, t in config.THEMES.items()}


def score_text(text):
    """Return {theme_key: score}. Phrases weigh double -- they are less ambiguous."""
    blob = (text or "").lower()
    return {key: 2 * len(ph.findall(blob)) + len(wd.findall(blob))
            for key, (ph, wd) in _PATTERNS.items()}


def classify(text):
    """Best-matching theme, or UNTHEMED when nothing in the legend is mentioned."""
    scores = score_text(text)
    best = max(scores, key=lambda k: (scores[k], -config.THEME_ORDER.index(k)))
    return best if scores[best] > 0 else UNTHEMED


def add_themes(df):
    out = df.copy()
    blob = (out["title"].fillna("") + " " + out["text"].fillna(""))
    out["theme"] = blob.map(classify)
    out["theme_label"] = out["theme"].map(lambda k: config.THEMES[k]["label"] if k else "Unthemed")
    return out


def for_export(df):
    """Columns safe to publish.

    review_id is only a content hash used for de-duplication, but a long hex
    string reads like an account number, so it does not travel into artifacts.
    """
    return df.drop(columns=[c for c in ("review_id", "theme") if c in df.columns])


def summarise(df, focus_days=7):
    """Volume and sentiment per theme for the focus week, with a prior-period delta."""
    df = df if "theme" in df.columns else add_themes(df)
    dates = pd.to_datetime(df["date"])
    end = dates.max()
    start = end - pd.Timedelta(days=focus_days - 1)

    focus = df[dates >= start]
    prior = df[dates < start]
    if len(focus) < 25:            # thin week (e.g. a fresh app): rank on everything
        focus, prior = df, df.iloc[0:0]

    themed = focus[focus["theme"] != UNTHEMED]
    prior_themed = prior[prior["theme"] != UNTHEMED]

    themes = []
    for key, meta in config.THEMES.items():
        rows = themed[themed["theme"] == key]
        share = len(rows) / len(themed) if len(themed) else 0.0
        prior_rows = prior_themed[prior_themed["theme"] == key]
        prior_share = len(prior_rows) / len(prior_themed) if len(prior_themed) else None
        themes.append({
            "key": key,
            "label": meta["label"],
            "blurb": meta["blurb"],
            "n": len(rows),
            "share": share,
            "avg_rating": round(rows["rating"].mean(), 2) if len(rows) else None,
            "neg_pct": round(100 * (rows["rating"] <= 2).mean()) if len(rows) else 0,
            "delta_pp": None if prior_share is None else round(100 * (share - prior_share), 1),
        })
    themes.sort(key=lambda t: t["n"], reverse=True)

    return {
        "window_start": dates.min().date().isoformat(),
        "window_end": end.date().isoformat(),
        "focus_start": pd.to_datetime(focus["date"]).min().date().isoformat(),
        "focus_end": end.date().isoformat(),
        "total": len(df),
        "focus_total": len(focus),
        "focus_avg_rating": round(focus["rating"].mean(), 2),
        "focus_neg_pct": round(100 * (focus["rating"] <= 2).mean()),
        "unthemed": int((focus["theme"] == UNTHEMED).sum()),
        "themes": themes,
        "focus_df": focus,
    }
