"""Strip personal data out of review text.

The strongest protection is structural: we never read the author field off the
store APIs at all, so no username ever enters the CSV. This module handles the
rest -- identifiers people type into the review body themselves.
"""
import re

# Order matters: URLs and emails are consumed before the looser handle/number rules.
_RULES = [
    (re.compile(r"https?://\S+|www\.\S+", re.I), "[link]"),
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.]{2,}"), "[email]"),
    (re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b"), "[pan]"),                       # PAN card
    (re.compile(r"\b[\w.\-]{2,}@[a-z]{2,}\b"), "[upi]"),                       # UPI vpa
    (re.compile(r"(?<![\w])@[A-Za-z0-9_.]{2,}"), "[handle]"),                  # social handle
    (re.compile(r"(?<!\d)(?:\+?91[\s-]?)?[6-9]\d{9}(?!\d)"), "[phone]"),       # IN mobile
    (re.compile(r"(?<!\d)\d{8,}(?!\d)"), "[id]"),                              # aadhaar / acct / client no
    (re.compile(r"\b(?:client|user|account|folio|ticket|order|ref(?:erence)?)\s*"
                r"(?:id|no\.?|number|#)\s*[:\-]?\s*[A-Za-z0-9][A-Za-z0-9\-/]{3,}", re.I), "[id]"),
    (re.compile(r"\b(?:my name is|this is|i am|name[:\-])\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?", re.I), "[name]"),
]

_WHITESPACE = re.compile(r"\s+")


def scrub(text):
    """Return text with personal identifiers replaced by neutral placeholders."""
    if not text:
        return ""
    out = str(text)
    for pattern, replacement in _RULES:
        out = pattern.sub(replacement, out)
    return _WHITESPACE.sub(" ", out).strip()


def has_pii(text):
    """True if any rule still matches -- used as a final guard on artifacts."""
    return any(p.search(str(text or "")) for p, _ in _RULES[:7])


if __name__ == "__main__":
    samples = [
        "Contact me at riya.k@gmail.com or 9876543210, my PAN is ABCDE1234F",
        "Pay to rahul@ybl, client id GR8823771 not resolved. See https://groww.in/x",
        "My name is Arjun Mehta and my account 123456789012 is blocked",
    ]
    for s in samples:
        print(scrub(s))
