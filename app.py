"""Streamlit front end for the weekly review pulse.

Run locally:   streamlit run app.py
Deploy:        point Streamlit Community Cloud at this repo, main file app.py
"""
import os
import urllib.parse
from datetime import datetime

import streamlit as st

from pulse import config
from pulse.fetch import fetch_reviews
from pulse.mailer import build_message, note_html, subject_for
from pulse.note import build_note, word_count
from pulse.themes import add_themes, for_export, summarise

st.set_page_config(page_title=f"{config.APP_NAME} Review Pulse",
                   page_icon="\U0001F4C8", layout="wide")

GREEN = "#00D09C"
RED = "#EB5B3C"

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

:root {
  --g-green:#00D09C; --g-green-dark:#00B386; --g-ink:#121212;
  --g-muted:#7C7E8C; --g-line:#E9E9EB; --g-red:#EB5B3C; --g-bg:#F7F7F7;
}
html, body, [class*="css"], .stMarkdown, .stButton button { font-family:'Inter',-apple-system,sans-serif; }
.stApp { background:var(--g-bg); }
header[data-testid="stHeader"] { background:transparent; }
footer { visibility:hidden; }
.block-container { padding-top:1.2rem; max-width:1180px; }

/* ---- top bar ---- */
.g-nav { display:flex; align-items:center; gap:12px; background:#fff; border:1px solid var(--g-line);
         border-radius:12px; padding:14px 20px; margin-bottom:18px; }
.g-logo { width:30px; height:30px; border-radius:50%; background:var(--g-green);
          display:flex; align-items:center; justify-content:center; color:#fff;
          font-weight:700; font-size:17px; }
.g-word { font-weight:700; font-size:19px; color:var(--g-ink); letter-spacing:-.3px; }
.g-tag  { font-size:12px; font-weight:600; color:var(--g-green-dark); background:rgba(0,208,156,.12);
          padding:4px 10px; border-radius:20px; }
.g-when { margin-left:auto; font-size:13px; color:var(--g-muted); }

/* ---- cards ---- */
.g-card { background:#fff; border:1px solid var(--g-line); border-radius:12px; padding:18px 20px; height:100%; }
.g-kpi { min-height:108px; }
.g-kpi-label { font-size:12px; color:var(--g-muted); font-weight:500; margin-bottom:6px; }
.g-kpi-value { font-size:26px; font-weight:700; color:var(--g-ink); line-height:1.15; letter-spacing:-.5px; }
/* word values (a theme name) would wrap to three lines at the number size */
.g-kpi-value.text { font-size:17px; line-height:1.3; }
.g-kpi-sub { font-size:12px; color:var(--g-muted); margin-top:4px; }

.g-h { font-size:13px; font-weight:600; color:var(--g-muted); text-transform:uppercase;
       letter-spacing:.6px; margin:26px 0 12px; }

/* ---- theme rows ----
   Grid, not flex: fixed pixel columns starved the bar of width at narrow widths. */
.g-row { display:grid; grid-template-columns:minmax(110px,1.5fr) minmax(60px,2.2fr) 40px 104px;
         align-items:center; gap:12px; padding:11px 0; border-bottom:1px solid var(--g-line); }
.g-row:last-child { border-bottom:none; }
.g-row-name { font-size:14px; font-weight:600; color:var(--g-ink); }
.g-bar { height:8px; background:#F0F0F2; border-radius:6px; overflow:hidden; }
.g-bar span { display:block; height:100%; border-radius:6px; }
.g-row-n { text-align:right; font-size:14px; font-weight:600; color:var(--g-ink); }
.g-row-meta { text-align:right; font-size:11px; color:var(--g-muted); white-space:nowrap; }

/* ---- quotes ---- */
.g-quote { background:#fff; border:1px solid var(--g-line); border-left:3px solid var(--g-green);
           border-radius:10px; padding:14px 16px; margin-bottom:10px; }
.g-quote p { font-size:14px; color:var(--g-ink); margin:0 0 8px; line-height:1.55; }
.g-quote span { font-size:12px; color:var(--g-muted); }

/* ---- note sheet ---- */
.g-sheet { background:#fff; border:1px solid var(--g-line); border-radius:12px; padding:26px 30px; }
.g-sheet h1 { font-size:21px; margin:0 0 6px; color:var(--g-ink); }
.g-sheet h2 { font-size:13px; text-transform:uppercase; letter-spacing:.6px;
              color:var(--g-muted); margin:22px 0 10px; }
.g-sheet blockquote { border-left:3px solid var(--g-green); margin:0 0 10px; padding:2px 0 2px 14px; color:#333; }
.g-sheet li { margin-bottom:7px; }

/* ---- controls ---- */
.stButton button { background:var(--g-green); color:#fff; border:none; border-radius:8px;
                   font-weight:600; padding:.5rem 1.1rem; }
.stButton button:hover { background:var(--g-green-dark); color:#fff; }
.stDownloadButton button { background:#fff; color:var(--g-ink); border:1px solid var(--g-line);
                           border-radius:8px; font-weight:600; }
section[data-testid="stSidebar"] { background:#fff; border-right:1px solid var(--g-line); }
</style>
""", unsafe_allow_html=True)


@st.cache_data(ttl=3600, show_spinner=False)
def load_reviews(weeks, sources):
    return fetch_reviews(weeks_back=weeks, sources=sources)


def api_key():
    try:
        if "ANTHROPIC_API_KEY" in st.secrets:
            return st.secrets["ANTHROPIC_API_KEY"]
    except Exception:
        pass
    return os.getenv("ANTHROPIC_API_KEY")


def card(label, value, sub="", text_value=False):
    size = "g-kpi-value text" if text_value else "g-kpi-value"
    return (f'<div class="g-card g-kpi"><div class="g-kpi-label">{label}</div>'
            f'<div class="{size}">{value}</div>'
            f'<div class="g-kpi-sub">{sub}</div></div>')


# --------------------------------------------------------------------------- sidebar
with st.sidebar:
    st.markdown("### Controls")
    weeks = st.slider("Look-back window (weeks)", 4, 12, config.WEEKS_BACK,
                      help="The brief asks for 8-12 weeks. Longer windows take longer to fetch.")
    picked = st.multiselect("Stores", ["App Store", "Play Store"],
                            default=["App Store", "Play Store"])
    to_addr = st.text_input("Email the note to", config.MAIL_TO)
    if st.button("Refresh reviews", use_container_width=True):
        load_reviews.clear()
    with st.expander("Theme legend"):
        for meta in config.THEMES.values():
            st.markdown(f"**{meta['label']}** — {meta['blurb']}")

sources = tuple(s for s, name in (("apple", "App Store"), ("play", "Play Store")) if name in picked)

st.markdown(f"""
<div class="g-nav">
  <div class="g-logo">G</div>
  <div class="g-word">{config.APP_NAME}</div>
  <div class="g-tag">Review Pulse</div>
  <div class="g-when">Generated {datetime.now():%d %b %Y, %H:%M}</div>
</div>""", unsafe_allow_html=True)

if not sources:
    st.warning("Pick at least one store in the sidebar.")
    st.stop()

with st.spinner(f"Importing the last {weeks} weeks of public reviews…"):
    df = load_reviews(weeks, sources)

if df.empty:
    st.error("No reviews came back. Check the app ids in `pulse/config.py`.")
    st.stop()

df = add_themes(df)
stats = summarise(df)
note_md, payload = build_note(stats, api_key=api_key())

# --------------------------------------------------------------------------- KPIs
cols = st.columns(4)
coverage = 100 - round(100 * stats["unthemed"] / max(stats["focus_total"], 1))
kpis = [
    ("Reviews this week", f"{stats['focus_total']:,}", f"{stats['total']:,} in the {weeks}-week window", False),
    ("Average rating", f"{stats['focus_avg_rating']}★", f"{stats['focus_neg_pct']}% rated 1-2★", False),
    ("Top theme", stats["themes"][0]["label"], f"{stats['themes'][0]['n']} reviews this week", True),
    ("Themed coverage", f"{coverage}%", f"{stats['unthemed']} short reviews unthemed", False),
]
for col, (label, value, sub, is_text) in zip(cols, kpis):
    col.markdown(card(label, value, sub, is_text), unsafe_allow_html=True)

# --------------------------------------------------------------------------- themes
st.markdown('<div class="g-h">Themes this week</div>', unsafe_allow_html=True)
peak = max((t["n"] for t in stats["themes"]), default=1) or 1
rows = []
for t in stats["themes"]:
    colour = RED if t["neg_pct"] >= 50 else GREEN
    delta = "" if t["delta_pp"] is None else f" · {t['delta_pp']:+}pp"
    rating = t["avg_rating"] if t["avg_rating"] is not None else "–"
    width = 100 * t["n"] / peak
    rows.append(
        f'<div class="g-row"><div class="g-row-name">{t["label"]}</div>'
        f'<div class="g-bar"><span style="width:{width:.0f}%;background:{colour}"></span></div>'
        f'<div class="g-row-n">{t["n"]}</div>'
        f'<div class="g-row-meta">{rating}★ · {t["neg_pct"]}% neg{delta}</div></div>'
    )
st.markdown(f'<div class="g-card">{"".join(rows)}</div>', unsafe_allow_html=True)

# --------------------------------------------------------------------------- note + quotes
left, right = st.columns([3, 2], gap="medium")

with left:
    st.markdown('<div class="g-h">The weekly note</div>', unsafe_allow_html=True)
    # One HTML string, so the sheet wrapper actually contains the note: Streamlit
    # puts each st.markdown call in its own container, so a split-open div would not nest.
    st.markdown(f'<div class="g-sheet">{note_html(note_md)}</div>', unsafe_allow_html=True)
    st.caption(f"{word_count(note_md)} words (cap {config.MAX_WORDS}) · writer: {payload['writer']}")

with right:
    st.markdown('<div class="g-h">In their words</div>', unsafe_allow_html=True)
    for q in payload["quotes"]:
        st.markdown(
            f'<div class="g-quote"><p>“{q["text"]}”</p>'
            f'<span>{q["rating"]}★ · {q["source"]} · {q["theme"]}</span></div>',
            unsafe_allow_html=True)

    st.markdown('<div class="g-h">Email draft</div>', unsafe_allow_html=True)
    subject = subject_for(stats)
    st.markdown(f'<div class="g-card"><div class="g-kpi-label">To</div>'
                f'<div style="font-size:14px;font-weight:600;margin-bottom:10px">{to_addr}</div>'
                f'<div class="g-kpi-label">Subject</div>'
                f'<div style="font-size:14px;font-weight:600">{subject}</div></div>',
                unsafe_allow_html=True)
    mailto = (f"mailto:{urllib.parse.quote(to_addr)}"
              f"?subject={urllib.parse.quote(subject)}&body={urllib.parse.quote(note_md)}")
    st.markdown(f'<a href="{mailto}" target="_blank" style="display:inline-block;margin-top:10px;'
                f'background:{GREEN};color:#fff;padding:9px 16px;border-radius:8px;'
                f'font-weight:600;font-size:14px;text-decoration:none">Open in mail app</a>',
                unsafe_allow_html=True)

# --------------------------------------------------------------------------- downloads
st.markdown('<div class="g-h">Artifacts</div>', unsafe_allow_html=True)
d1, d2, d3 = st.columns(3)
d1.download_button("Weekly note (.md)", note_md, "weekly_note.md", "text/markdown",
                   use_container_width=True)
d2.download_button("Reviews (.csv)", for_export(df).to_csv(index=False).encode("utf-8"),
                   "reviews.csv", "text/csv", use_container_width=True)
d3.download_button("Email draft (.eml)", bytes(build_message(note_md, stats, to_addr=to_addr)),
                   "weekly_email.eml", "message/rfc822", use_container_width=True)

with st.expander(f"Browse the {len(df):,} reviews behind this note (no personal data)"):
    st.dataframe(df[["date", "source", "rating", "theme_label", "text"]],
                 use_container_width=True, hide_index=True, height=380)
