# Groww Review Pulse

Turns the last 8–12 weeks of **public** App Store and Play Store reviews into a
one-page weekly note — top themes, real user quotes, three things to do — and
drafts the email that carries it.

One command, no manual steps:

```bash
python run_weekly.py
```

| Who | What they get |
| --- | --- |
| Product / Growth | What to fix next, ranked by this week's volume and negativity |
| Support | The exact complaints users are posting, and the wording they use |
| Leadership | A 250-word health pulse with a week-on-week delta |

---

## Quickstart

```bash
pip install -r requirements.txt
```

Build this week's note, CSV and email draft:

```bash
python run_weekly.py
```

Open the dashboard:

```bash
streamlit run app.py
```

Nothing above needs an API key or a login. See [Optional: LLM writer](#optional-llm-writer).

---

## How to re-run for a new week

Run the same command again. There is nothing to edit between weeks — the window
is always relative to today, and every output is overwritten in place.

```bash
python run_weekly.py
```

Each run writes into `output/`:

| File | What it is |
| --- | --- |
| `weekly_note.md` | The one-page note (≤250 words) — **the deliverable** |
| `weekly_note_<YYYY-MM-DD>.md` | Same note, archived under the focus-week end date |
| `weekly_email.eml` | Email draft — double-click to open in any mail client |
| `weekly_email.txt` | Same draft as plain text, for pasting or screenshotting |
| `reviews.csv` | Every review used, PII-scrubbed (git-ignored; large) |

Useful flags:

```bash
python run_weekly.py --weeks 8              # shorter look-back window
python run_weekly.py --to team@example.com  # address the draft to someone else
python run_weekly.py --csv output/reviews.csv   # rebuild the note, skip fetching
python run_weekly.py --send                 # actually send (see Sending, below)
```

**Fully unattended:** [`.github/workflows/weekly-pulse.yml`](.github/workflows/weekly-pulse.yml)
runs the same command every Monday at 04:00 UTC, uploads the artifacts and commits
the new note back to the repo. Nothing to trigger by hand.

---

## Theme legend

Every review is scored against five fixed themes and assigned to its
best match. The buckets never change, so the week-on-week delta means something.

| Theme | Covers |
| --- | --- |
| **Onboarding & KYC** | Sign-up, identity verification, document upload, login and app access |
| **Payments & Withdrawals** | Adding money, UPI and bank transfers, redemptions, payouts, stuck or blocked funds |
| **Orders & Investing** | Placing and executing orders, SIPs, IPOs, F&O positions, charts, portfolio |
| **App Performance & UX** | Crashes, slowness, loading errors, server issues, ads, interface changes |
| **Charges, Statements & Support** | Brokerage and AMC charges, P&L and tax statements, customer support response |

A review that mentions none of the five is left **unthemed** rather than forced
into a bucket. That is normal and expected: most Play Store reviews are three
words long ("nice", "good app"). Coverage is ~78% of reviews with 10+ words, and
the dashboard reports the unthemed count so the number is never hidden.

Scoring is keyword-based and deterministic — phrases count double, single words
count once, highest score wins. The full keyword lists are in
[`pulse/config.py`](pulse/config.py); edit them there and the whole pipeline
follows. Rules were chosen over model-clustering on purpose: a bucket that
silently redefines itself makes the trend line meaningless.

---

## No personal data

The brief forbids usernames, emails and IDs in any artifact. Three layers:

1. **Structural** — the author field is never read off either store API, so no
   username can enter the pipeline in the first place.
2. **Scrubbing** — [`pulse/pii.py`](pulse/pii.py) redacts emails, phone numbers,
   PAN numbers, UPI handles, social handles, URLs, long digit runs and
   "my name is …" patterns from every review body at import time.
3. **Gate** — the note is re-checked before the email is built; the run aborts
   rather than mailing anything that still matches. Exported CSVs also drop the
   internal de-duplication hash, since a long hex string reads like an account number.

Both sources are open, public endpoints. Nothing logs in and nothing scrapes a
gated page.

---

## Optional: LLM writer

Without a key the note is written by a deterministic template — good enough to
run forever unattended, and what produced the committed sample.

With `ANTHROPIC_API_KEY` set, Claude writes the headline, theme insights and
action ideas, and picks the quotes, under a prompt that fixes the tone (calm,
factual, internal-memo voice; no hype) and the shape (3 themes, 3 quotes,
3 actions, under 200 words). The stats are computed in Python and passed in as
facts, so the model summarises and selects but never invents a number.

```bash
export ANTHROPIC_API_KEY=your-key-here     # Windows: setx ANTHROPIC_API_KEY your-key-here
python run_weekly.py
```

The run prints which writer produced the note, and so does the note's own footer.
If the API call fails for any reason, the run falls back to the template rather
than failing.

---

## Deploy to Streamlit Community Cloud

1. Push this repo to GitHub.
2. On [share.streamlit.io](https://share.streamlit.io): **New app** → pick the repo
   → main file `app.py` → **Deploy**.
3. Optional: **Settings → Secrets** → paste `ANTHROPIC_API_KEY = "your-key-here"`
   (see [`.streamlit/secrets.toml.example`](.streamlit/secrets.toml.example)).
4. Set your own recipient there too, so it never lands in a public repo:
   `MAIL_TO = "you@yourdomain.com"`. Streamlit exposes top-level secrets as
   environment variables, which is exactly what `pulse/config.py` reads.

`requirements.txt` and `.streamlit/config.toml` are already set up. The first
load fetches ~10k reviews and takes about 40 seconds; results are cached for an
hour, and **Refresh reviews** in the sidebar clears the cache.

---

## Sending the email

Default behaviour is **draft only** — an automated run can never mail anyone by
accident. To deliver it, set SMTP credentials and pass `--send`:

```bash
export SMTP_HOST=smtp.gmail.com SMTP_PORT=587
export SMTP_USER=you@gmail.com SMTP_PASS=your-app-password
python run_weekly.py --send
```

In the dashboard, **Open in mail app** opens the draft pre-filled in your mail
client, and **Email draft (.eml)** downloads it.

---

## Configuration

Everything tunable lives in [`pulse/config.py`](pulse/config.py), and each value
can be overridden by an environment variable of the same name.

| Setting | Default | Meaning |
| --- | --- | --- |
| `APPLE_APP_ID` | `1404871703` | Groww on the App Store |
| `PLAY_PACKAGE` | `com.nextbillion.groww` | Groww on Google Play |
| `STORE_COUNTRY` / `STORE_LANG` | `in` / `en` | Storefront to read |
| `WEEKS_BACK` | `12` | Look-back window |
| `MAIL_TO` | `you@example.com` | Who the draft is addressed to — set this, don't hardcode it |
| `ANTHROPIC_MODEL` | `claude-sonnet-5` | Model for the LLM writer |

Point it at a different app by changing the two ids — nothing else is
Groww-specific except the theme keywords.

---

## Layout

```
app.py              Streamlit dashboard
run_weekly.py       One-command pipeline: import -> group -> note -> draft
pulse/
  config.py         App ids, window, the five themes and their keywords
  fetch.py          Public App Store RSS + Play Store, paged to the cutoff
  pii.py            Redaction rules, and the guard used before sending
  themes.py         Keyword scoring, assignment, weekly stats and deltas
  note.py           Quote selection, LLM and rules writers, markdown renderer
  mailer.py         Builds the .eml draft; optional SMTP send
data/
  reviews_sample.csv  360-row redacted sample, stratified across all themes
output/             Generated each run
```

### A note on source coverage

Apple's public RSS feed only exposes its most recent ~500 reviews, so the App
Store contributes roughly the last three weeks regardless of the window you ask
for; Play Store pages back the full 12. The note's footer always states the real
date range rather than the requested one.
