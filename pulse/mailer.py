"""Build the weekly email as a draft file, and optionally send it.

Default behaviour is draft-only: the run writes a .eml you can open in any mail
client and send yourself. Sending over SMTP is opt-in via --send so an automated
weekly run can never mail anyone by accident.
"""
import os
import re
import smtplib
from email.message import EmailMessage

from . import config
from .pii import has_pii


def subject_for(stats):
    return (f"{config.APP_NAME} weekly review pulse - "
            f"{stats['focus_start']} to {stats['focus_end']}")


def note_html(md):
    """Small converter for the fixed subset of markdown the note emits."""
    out, in_list = [], False
    for line in md.split("\n"):
        if line.startswith("# "):
            html = f'<h1 style="font-size:20px;margin:0 0 4px">{line[2:]}</h1>'
        elif line.startswith("## "):
            html = f'<h2 style="font-size:14px;text-transform:uppercase;letter-spacing:.5px;color:#7c7e8c;margin:20px 0 8px">{line[3:]}</h2>'
        elif re.match(r"^\d+\. ", line):
            html = f'<li style="margin:0 0 6px">{re.sub(r"^\d+\. ", "", line)}</li>'
        elif line.startswith("> "):
            html = f'<div style="margin:0;padding:2px 0 2px 12px;border-left:3px solid #00d09c">{line[2:]}</div>'
        elif not line.strip():
            html = ""
        else:
            html = f'<p style="margin:0 0 10px">{line}</p>'

        is_item = html.startswith("<li")
        if is_item and not in_list:
            out.append('<ol style="margin:0 0 10px;padding-left:20px">')
        elif in_list and not is_item:
            out.append("</ol>")
        in_list = is_item
        out.append(html)
    if in_list:
        out.append("</ol>")

    body = "\n".join(x for x in out if x)
    body = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", body)
    body = re.sub(r"(?<![\*\w])\*(.+?)\*(?!\*)", r"<em>\1</em>", body)
    return ('<div style="font-family:Inter,Helvetica,Arial,sans-serif;font-size:14px;'
            'line-height:1.55;color:#121212;max-width:640px">' + body + "</div>")


def build_message(note_md, stats, to_addr=None, from_addr=None):
    """Return an EmailMessage with plain-text and HTML parts."""
    to_addr = to_addr or config.MAIL_TO
    from_addr = from_addr or config.MAIL_FROM
    if has_pii(note_md):
        raise ValueError("refusing to build email: note still contains personal data")

    msg = EmailMessage()
    msg["Subject"] = subject_for(stats)
    msg["To"] = to_addr
    msg["From"] = from_addr
    msg.set_content(note_md)
    msg.add_alternative(note_html(note_md), subtype="html")
    return msg


def save_draft(msg, path):
    """Write the message as a .eml draft (double-click to open in a mail client)."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "wb") as fh:
        fh.write(bytes(msg))
    return path


def send(msg):
    """Send over SMTP. Requires SMTP_HOST / SMTP_USER / SMTP_PASS in the environment."""
    host = os.environ["SMTP_HOST"]
    port = int(os.getenv("SMTP_PORT", "587"))
    user, password = os.environ["SMTP_USER"], os.environ["SMTP_PASS"]
    with smtplib.SMTP(host, port, timeout=30) as server:
        server.starttls()
        server.login(user, password)
        server.send_message(msg)
    return msg["To"]
