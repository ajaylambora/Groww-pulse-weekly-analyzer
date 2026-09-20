"""One command, start to finish: import -> group -> write note -> draft email.

    python run_weekly.py

Re-run it any week with no arguments and no edits. Every step is idempotent:
outputs are overwritten in place and also archived under the focus-week stamp.
"""
import argparse
import os
import sys

from pulse import config
from pulse.fetch import fetch_reviews
from pulse.mailer import build_message, save_draft, send, subject_for
from pulse.note import build_note, word_count
from pulse.pii import has_pii
from pulse.themes import add_themes, for_export, summarise


def parse_args(argv=None):
    p = argparse.ArgumentParser(description="Build the weekly app-review pulse.")
    p.add_argument("--weeks", type=int, default=config.WEEKS_BACK,
                   help=f"look-back window in weeks (default {config.WEEKS_BACK})")
    p.add_argument("--out", default=config.OUTPUT_DIR, help="output directory")
    p.add_argument("--to", default=config.MAIL_TO, help="email recipient for the draft")
    p.add_argument("--send", action="store_true",
                   help="actually send over SMTP (needs SMTP_HOST/USER/PASS); default is draft only")
    p.add_argument("--csv", help="skip fetching and read reviews from this CSV instead")
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    os.makedirs(args.out, exist_ok=True)

    print(f"[1/4] Importing reviews (last {args.weeks} weeks)...")
    if args.csv:
        import pandas as pd
        df = pd.read_csv(args.csv).fillna("")
        print(f"      loaded {len(df)} rows from {args.csv}")
    else:
        df = fetch_reviews(weeks_back=args.weeks)
    if df.empty:
        print("      no reviews returned - check the app ids in pulse/config.py")
        return 1
    by_source = ", ".join(f"{k}: {v}" for k, v in df["source"].value_counts().items())
    print(f"      {len(df)} reviews  ({by_source})  {df['date'].min()} -> {df['date'].max()}")

    print("[2/4] Grouping into themes...")
    df = add_themes(df)
    stats = summarise(df)
    for t in stats["themes"]:
        print(f"      {t['label']:<32} {t['n']:>4}  avg {t['avg_rating']}  {t['neg_pct']}% negative")
    print(f"      unthemed in focus week: {stats['unthemed']} of {stats['focus_total']}")

    print("[3/4] Writing the weekly note...")
    note_md, payload = build_note(stats)
    words = word_count(note_md)
    print(f"      {words} words (cap {config.MAX_WORDS}), writer: {payload['writer']}")

    if has_pii(note_md):
        print("      ! note failed the PII check - aborting before anything is written")
        return 2

    stamp = stats["focus_end"]
    csv_path = os.path.join(args.out, "reviews.csv")
    note_path = os.path.join(args.out, "weekly_note.md")
    for_export(df).to_csv(csv_path, index=False, encoding="utf-8")
    with open(note_path, "w", encoding="utf-8") as fh:
        fh.write(note_md + "\n")
    with open(os.path.join(args.out, f"weekly_note_{stamp}.md"), "w", encoding="utf-8") as fh:
        fh.write(note_md + "\n")
    print(f"      wrote {csv_path} and {note_path}")

    print("[4/4] Drafting the email...")
    msg = build_message(note_md, stats, to_addr=args.to)
    eml_path = save_draft(msg, os.path.join(args.out, "weekly_email.eml"))
    with open(os.path.join(args.out, "weekly_email.txt"), "w", encoding="utf-8") as fh:
        fh.write(f"To: {args.to}\nSubject: {subject_for(stats)}\n\n{note_md}\n")
    print(f"      draft saved to {eml_path}  (To: {args.to})")

    if args.send:
        try:
            print(f"      sent to {send(msg)}")
        except KeyError as missing:
            print(f"      ! cannot send: {missing} is not set; the draft is still on disk")
            return 3
    else:
        print("      not sent (draft only) - pass --send with SMTP_* set to deliver it")

    print("\nDone.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
