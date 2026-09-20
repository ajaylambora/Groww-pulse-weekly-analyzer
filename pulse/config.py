"""Single place for everything you might want to change week to week."""
import os

APP_NAME = "Groww"

# Public store identifiers (no login required to read these).
APPLE_APP_ID = os.getenv("APPLE_APP_ID", "1404871703")   # Groww Stocks, Mutual Fund, IPO
PLAY_PACKAGE = os.getenv("PLAY_PACKAGE", "com.nextbillion.groww")
COUNTRY = os.getenv("STORE_COUNTRY", "in")
LANG = os.getenv("STORE_LANG", "en")

# Look-back window for the pulse (brief asks for 8-12 weeks).
WEEKS_BACK = int(os.getenv("WEEKS_BACK", "12"))

# How hard to pull. Apple's public RSS caps out around 500 reviews (10 pages).
APPLE_MAX_PAGES = int(os.getenv("APPLE_MAX_PAGES", "10"))
PLAY_HARD_CAP = int(os.getenv("PLAY_HARD_CAP", "20000"))   # safety net, not a target

# Note constraints from the brief.
MAX_WORDS = 250
TOP_THEMES = 3
N_QUOTES = 3
N_ACTIONS = 3

# LLM (optional). Without a key the pipeline falls back to a deterministic writer.
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5")

# Email draft. Nothing is sent unless you explicitly pass --send.
MAIL_TO = os.getenv("MAIL_TO", "you@example.com")   # set MAIL_TO in env / Streamlit secrets
MAIL_FROM = os.getenv("MAIL_FROM", MAIL_TO)

OUTPUT_DIR = os.getenv("OUTPUT_DIR", "output")

# ---------------------------------------------------------------------------
# Exactly five themes. Every review lands in at most one of them; anything with
# no keyword hit is left "unthemed" rather than forced into a bucket.
# phrases count double because they are far less ambiguous than single words.
# ---------------------------------------------------------------------------
THEMES = {
    "onboarding_kyc": {
        "label": "Onboarding & KYC",
        "blurb": "Sign-up, identity verification, document upload, login and app access.",
        "phrases": ["account opening", "open account", "video kyc", "kyc process", "kyc pending",
                    "sign up", "signing up", "new account", "verification process", "not able to login",
                    "unable to login", "log in", "sign in", "demat account", "account is blocked",
                    "account blocked", "account closed", "close my account"],
        "words": ["kyc", "aadhaar", "aadhar", "pan", "esign", "signup", "register", "registration",
                  "onboarding", "verification", "verify", "verified", "selfie", "nominee", "ipv",
                  "activation", "activate", "login", "otp", "mpin", "password", "biometric"],
    },
    "payments_funds": {
        "label": "Payments & Withdrawals",
        "blurb": "Adding money, UPI and bank transfers, redemptions, payouts and stuck or blocked funds.",
        "phrases": ["add money", "add funds", "money not", "not credited", "not received",
                    "withdrawal request", "withdraw money", "payment failed", "amount debited",
                    "money debited", "bank account", "net banking", "auto pay", "stuck in",
                    "my money", "money blocked", "amount blocked", "not settled", "money back",
                    "paisa block", "fund transfer"],
        "words": ["payment", "upi", "netbanking", "deposit", "withdraw", "withdrawal", "redeem",
                  "redemption", "payout", "refund", "debited", "credited", "neft", "imps", "rtgs",
                  "mandate", "autopay", "transfer", "wallet", "settlement", "settled", "unsettled",
                  "paisa", "paise", "funds", "blocked"],
    },
    "orders_trading": {
        "label": "Orders & Investing",
        "blurb": "Placing and executing orders, SIPs, IPOs, F&O positions, charts and portfolio.",
        "phrases": ["mutual fund", "order placed", "order not", "buy sell", "stop loss",
                    "limit order", "market order", "square off", "squared off", "ipo allotment",
                    "sip amount", "sip date", "price alert", "live price", "f&o", "profit and loss",
                    "trading view", "option chain"],
        "words": ["order", "orders", "buy", "sell", "trade", "trading", "stock", "stocks", "share",
                  "shares", "sip", "ipo", "allotment", "intraday", "delivery", "gtt", "margin",
                  "chart", "charts", "candle", "watchlist", "portfolio", "holding", "holdings",
                  "nav", "units", "executed", "position", "positions", "fno", "equity", "commodity",
                  "nifty", "expiry", "profit", "loss", "returns", "invest", "investment", "investing"],
    },
    "app_performance": {
        "label": "App Performance & UX",
        "blurb": "Crashes, slowness, loading errors, server issues, ads and interface changes.",
        "phrases": ["not working", "app crashes", "keeps crashing", "very slow", "so slow",
                    "server down", "not loading", "app is not", "after update", "new update",
                    "force close", "user interface", "dark mode", "too many ads", "worst app",
                    "app hangs"],
        "words": ["crash", "crashes", "crashing", "slow", "lag", "lagging", "laggy", "hang", "hangs",
                  "freeze", "frozen", "stuck", "error", "bug", "bugs", "glitch", "server", "loading",
                  "unresponsive", "ui", "ux", "design", "layout", "notification", "notifications",
                  "ads", "popup", "popups", "ipad", "tablet", "version", "screen", "button"],
    },
    "charges_support": {
        "label": "Charges, Statements & Support",
        "blurb": "Brokerage and AMC charges, P&L and tax statements, and customer support response.",
        "phrases": ["hidden charges", "extra charges", "dp charges", "amc charges", "brokerage charges",
                    "customer care", "customer support", "customer service", "costumer service",
                    "customer executive", "call back", "no response", "no reply", "capital gain",
                    "contract note", "tax report", "p and l", "raise a ticket", "never reply",
                    "not resolved", "help desk"],
        "words": ["charge", "charges", "charged", "fee", "fees", "brokerage", "amc", "hidden",
                  "statement", "statements", "ledger", "pnl", "tax", "support", "helpline",
                  "grievance", "complaint", "ticket", "escalate", "deducted", "agent", "executive",
                  "unresolved"],
    },
}
THEME_ORDER = list(THEMES)
