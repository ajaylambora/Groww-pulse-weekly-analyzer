"""Turn theme stats into the one-page weekly note.

Two writers produce the same payload shape, so the renderer is shared:
  * an LLM writer (Anthropic) when a key is available -- better prose and real
    quote judgement;
  * a deterministic writer otherwise, so an unattended weekly run never fails
    just because a key is missing.
"""
import json
import os
import re

from . import config
from .pii import has_pii, scrub
from .themes import score_text

STAR = "★"


# --------------------------------------------------------------------------- quotes
def _quote_score(row, theme_key):
    text = row["text"]
    n = len(text)
    if not (60 <= n <= 240) or has_pii(text):
        return -1
    if sum(c.isascii() for c in text) / n < 0.85:   # keep the one-pager readable
        return -1
    if sum(c.isupper() for c in text) / n > 0.5:
        return -1
    specificity = score_text(text).get(theme_key, 0)
    sweetness = 1 - abs(n - 140) / 140              # favour a quotable middle length
    extremity = abs(row["rating"] - 3) / 2          # 1- and 5-star reviews say more
    return specificity + 2 * sweetness + extremity


def _trim(text, limit):
    if len(text) <= limit:
        return text
    return text[:limit].rsplit(" ", 1)[0].rstrip(",.;:") + "…"


def pick_quotes(focus_df, theme_keys, per_theme=1):
    """Best quote(s) per theme -- one voice per top theme beats three on one topic."""
    picked, seen = [], set()
    for key in theme_keys:
        rows = focus_df[focus_df["theme"] == key]
        scored = sorted(((_quote_score(r, key), r) for _, r in rows.iterrows()),
                        key=lambda x: x[0], reverse=True)
        taken = 0
        for score, r in scored:
            if score < 0:
                break
            if r["text"] in seen:
                continue
            seen.add(r["text"])
            picked.append({
                "text": _trim(scrub(r["text"]), 200),
                "rating": int(r["rating"]),
                "source": r["source"],
                "theme": config.THEMES[key]["label"],
            })
            taken += 1
            if taken >= per_theme:
                break
    return picked


# --------------------------------------------------------------------------- writers
_ACTIONS = {
    "onboarding_kyc": [
        ("Instrument the KYC drop-off funnel",
         "Log every step from PAN entry to activation and publish where applicants stall."),
        ("Show live status on the blocked-account screen",
         "Replace the generic under-review state with a reason and an expected date."),
    ],
    "payments_funds": [
        ("Publish a withdrawal status tracker",
         "Show settlement stage and expected credit date in-app so users stop guessing."),
        ("Alert proactively on stuck debits",
         "Notify when a debit has no matching credit after 24h, before the user writes in."),
    ],
    "orders_trading": [
        ("Audit order-rejection messages",
         "Replace generic failure codes with the actual reason and the next step."),
        ("Ship the chart and position gaps users keep naming",
         "Triage repeated asks on timeframes, squared-off positions and P&L views into one release."),
    ],
    "app_performance": [
        ("Gate the next release on a crash-rate budget",
         "Most complaints follow an update; hold rollout if crash or ANR rate regresses."),
        ("Cut the interruption load on the home screen",
         "Reduce promo surfaces users describe as ads and measure session drop-off."),
    ],
    "charges_support": [
        ("Put a charges breakdown next to every debit",
         "Itemise brokerage, DP and statutory fees inline so hidden-charge claims have an answer."),
        ("Set and show a first-response SLA in chat",
         "Users quote multi-hour waits; display queue position and honour a stated target."),
    ],
}


def _heuristic_payload(stats, quotes):
    top = stats["themes"][: config.TOP_THEMES]
    themed_total = stats["focus_total"] - stats["unthemed"]

    themes = []
    for t in top:
        bits = [f"{t['n']}/{themed_total} themed", f"{t['neg_pct']}% at 1-2{STAR}"]
        if t["delta_pp"] is not None and abs(t["delta_pp"]) >= 1:
            bits.append(f"{t['delta_pp']:+}pp vs prior weeks")
        themes.append(dict(t, insight=" · ".join(bits)))

    actions = []
    for t in top:
        title, detail = _ACTIONS[t["key"]][0 if t["neg_pct"] >= 50 else -1]
        actions.append({"title": title, "detail": detail})

    worst = max(top, key=lambda t: t["neg_pct"])
    headline = (f"{stats['focus_total']} reviews, avg {stats['focus_avg_rating']}{STAR}. "
                f"Sharpest pain is {worst['label'].lower()} at {worst['neg_pct']}% negative.")
    return {"headline": headline, "themes": themes, "quotes": quotes[: config.N_QUOTES],
            "actions": actions[: config.N_ACTIONS], "writer": "rules"}


_PROMPT = """You are writing an internal weekly review pulse for the {app} product team.

Tone: calm, factual, specific. Plain internal-memo voice. No marketing adjectives,
no exclamation marks, no hype. Write for a PM who has 60 seconds and needs to
decide what to fix next.

Window: {focus_start} to {focus_end}. {focus_total} reviews, average rating
{focus_avg}, {focus_neg}% rated 1-2 stars.

THEME STATS (already computed - do not recount, do not invent numbers):
{stats}

CANDIDATE QUOTES (verbatim, already stripped of personal data):
{quotes}

Return ONLY a JSON object, no prose around it:
{{
  "headline": "one sentence, max 22 words, naming the single most important shift",
  "themes": [{{"key": "<theme key from the stats above>",
               "insight": "max 24 words: what is happening and why it matters. Cite a number."}}],
  "quotes": [{{"index": <0-based index of a candidate quote>}}],
  "actions": [{{"title": "max 8 words, imperative",
                "detail": "max 22 words, concrete and testable"}}]
}}

Exactly {n_themes} themes (the highest-volume ones), exactly {n_quotes} quotes
(most informative, one per theme where possible), exactly {n_actions} actions.
Each action must follow from a theme above. Keep the total under 200 words.
Never include a name, email, phone number or account id."""


def _stat_lines(stats):
    out = []
    for t in stats["themes"]:
        delta = "no prior baseline" if t["delta_pp"] is None else f"{t['delta_pp']:+}pp vs prior weeks"
        out.append(f"- {t['key']} ({t['label']}): {t['n']} reviews, {t['share']:.0%} of themed, "
                   f"avg {t['avg_rating']}, {t['neg_pct']}% negative, {delta}")
    return "\n".join(out)


def _llm_payload(stats, quotes, api_key):
    import anthropic

    quote_lines = "\n".join(f"[{i}] ({q['rating']}{STAR}, {q['source']}, {q['theme']}) {q['text']}"
                            for i, q in enumerate(quotes))
    prompt = _PROMPT.format(
        app=config.APP_NAME, focus_start=stats["focus_start"], focus_end=stats["focus_end"],
        focus_total=stats["focus_total"], focus_avg=stats["focus_avg_rating"],
        focus_neg=stats["focus_neg_pct"], stats=_stat_lines(stats), quotes=quote_lines,
        n_themes=config.TOP_THEMES, n_quotes=config.N_QUOTES, n_actions=config.N_ACTIONS)

    msg = anthropic.Anthropic(api_key=api_key).messages.create(
        model=config.ANTHROPIC_MODEL, max_tokens=1200,
        messages=[{"role": "user", "content": prompt}])
    raw = re.sub(r"^```(?:json)?|```$", "", msg.content[0].text.strip(), flags=re.M).strip()
    data = json.loads(raw)

    by_key = {t["key"]: t for t in stats["themes"]}
    top = stats["themes"][: config.TOP_THEMES]
    themes = []
    for item in data["themes"][: config.TOP_THEMES]:
        base = by_key.get(item.get("key")) or top[len(themes)]
        themes.append(dict(base, insight=scrub(item["insight"])))

    chosen = []
    for item in data["quotes"][: config.N_QUOTES]:
        idx = item.get("index")
        if isinstance(idx, int) and 0 <= idx < len(quotes) and quotes[idx] not in chosen:
            chosen.append(quotes[idx])
    for q in quotes:                       # backfill if the model under-picked
        if len(chosen) >= config.N_QUOTES:
            break
        if q not in chosen:
            chosen.append(q)

    actions = [{"title": scrub(a["title"]), "detail": scrub(a["detail"])}
               for a in data["actions"][: config.N_ACTIONS]]
    return {"headline": scrub(data["headline"]), "themes": themes,
            "quotes": chosen[: config.N_QUOTES], "actions": actions, "writer": "llm"}


def build_payload(stats, api_key=None):
    """LLM writer when a key is available, deterministic writer otherwise."""
    top_keys = [t["key"] for t in stats["themes"][: config.TOP_THEMES]]
    candidates = pick_quotes(stats["focus_df"], top_keys, per_theme=1)
    for q in pick_quotes(stats["focus_df"], top_keys, per_theme=3):
        if q not in candidates:
            candidates.append(q)

    api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
    if api_key:
        try:
            return _llm_payload(stats, candidates, api_key)
        except Exception as exc:           # never break an unattended run
            print(f"  ! LLM writer failed ({type(exc).__name__}: {exc}) - using rules writer")
    return _heuristic_payload(stats, candidates)


# --------------------------------------------------------------------------- render
def word_count(md):
    return len(re.findall(r"\S+", re.sub(r"[#*_>|`]", " ", md)))


def render_markdown(payload, stats, quote_chars=200):
    lines = [
        f"# {config.APP_NAME} - Weekly Review Pulse",
        f"**{stats['focus_start']} to {stats['focus_end']}** | {stats['focus_total']} reviews | "
        f"avg {stats['focus_avg_rating']}{STAR} | {stats['focus_neg_pct']}% rated 1-2{STAR}",
        "",
        payload["headline"],
        "",
        "## Top themes",
    ]
    for i, t in enumerate(payload["themes"], 1):
        lines.append(f"{i}. **{t['label']}** - {t['insight']}")
    lines += ["", "## What users said"]
    for q in payload["quotes"]:
        lines += [f"> “{_trim(q['text'], quote_chars)}”",
                  f"> *{q['rating']}{STAR} - {q['source']} - {q['theme']}*", ""]
    lines.append("## Three things to do")
    for i, a in enumerate(payload["actions"], 1):
        lines.append(f"{i}. **{a['title']}** - {a['detail']}")
    lines += ["",
              f"<sub>Public App Store + Play Store reviews, {stats['window_start']} to "
              f"{stats['window_end']}. No personal data. Writer: {payload['writer']}.</sub>"]
    return "\n".join(lines)


def build_note(stats, api_key=None, max_words=None):
    """Render the note, tightening quotes until it fits the word budget."""
    max_words = max_words or config.MAX_WORDS
    payload = build_payload(stats, api_key)
    md = render_markdown(payload, stats)
    for quote_chars in (200, 170, 140, 115, 95, 80):
        md = render_markdown(payload, stats, quote_chars)
        if word_count(md) <= max_words:
            break
    return md, payload
