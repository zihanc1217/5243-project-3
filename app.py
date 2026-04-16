"""
A/B Test Web Application
========================

Implements two A/B tests for the "Designing and Conducting an Experiment"
project:

Experiment 1 — Discount / Offer Page (landing page)
    * Variant A: "Join Our Newsletter"           (no discount)
    * Variant B: "Join & Get 10% Off"            (discount incentive)
    * Metric:    conversion rate (email submit)

Experiment 2 — Form Length Test (registration page)
    * Variant A: Short form (email only)
    * Variant B: Long form  (name + email + school)
    * Metric:    submission rate

Users are randomly assigned to a variant on first visit.  Assignment is
persisted via a cookie so that the same user sees the same variant on
repeat visits.  The assignment can also be forced via a query string
parameter (``?group=A`` / ``?group=B``) for manual testing / sharing.

All impressions and conversions are logged to a SQLite database for
subsequent statistical analysis (see ``analysis.py``).
"""

from __future__ import annotations

import os
import random
import sqlite3
import uuid
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from flask import (
    Flask,
    g,
    jsonify,
    make_response,
    redirect,
    render_template,
    request,
    url_for,
)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = Path(os.environ.get("AB_DB_PATH", BASE_DIR / "ab_test.db"))

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-key-change-me")


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         TEXT    NOT NULL,
    experiment      TEXT    NOT NULL,   -- 'discount' or 'form_length'
    variant         TEXT    NOT NULL,   -- 'A' or 'B'
    event_type      TEXT    NOT NULL,   -- 'impression', 'conversion'
    created_at      TEXT    NOT NULL,
    user_agent      TEXT,
    referrer        TEXT,
    payload         TEXT               -- JSON-ish string for form content
);

CREATE INDEX IF NOT EXISTS idx_events_experiment_variant
    ON events (experiment, variant, event_type);
"""


def get_db() -> sqlite3.Connection:
    """Return a request-scoped SQLite connection."""
    if "db" not in g:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        g.db = conn
    return g.db


@app.teardown_appcontext
def close_db(_exception):  # noqa: D401 — Flask hook
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db() -> None:
    """Create the SQLite database and schema if not already present."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(DB_PATH)) as conn:
        conn.executescript(SCHEMA)
        conn.commit()


def log_event(
    user_id: str,
    experiment: str,
    variant: str,
    event_type: str,
    payload: str | None = None,
) -> None:
    """Insert a single tracking event."""
    db = get_db()
    db.execute(
        """
        INSERT INTO events
            (user_id, experiment, variant, event_type,
             created_at, user_agent, referrer, payload)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            user_id,
            experiment,
            variant,
            event_type,
            datetime.now(timezone.utc).isoformat(timespec="seconds"),
            request.headers.get("User-Agent", ""),
            request.referrer or "",
            payload,
        ),
    )
    db.commit()


# ---------------------------------------------------------------------------
# A/B assignment helpers
# ---------------------------------------------------------------------------

USER_COOKIE = "ab_user_id"
DISCOUNT_COOKIE = "ab_discount_variant"
FORM_COOKIE = "ab_form_variant"


def _resolve_variant(cookie_name: str, query_key: str = "group") -> str:
    """
    Resolve the A/B variant for the current request.

    Priority (highest to lowest):
        1. Explicit ``?group=A|B`` query-string override.
        2. Previously set cookie.
        3. Fresh random 50/50 assignment.
    """
    forced = request.args.get(query_key, "").upper().strip()
    if forced in {"A", "B"}:
        return forced

    cookie_val = request.cookies.get(cookie_name, "").upper()
    if cookie_val in {"A", "B"}:
        return cookie_val

    return random.choice(["A", "B"])


def _resolve_user_id() -> str:
    return request.cookies.get(USER_COOKIE) or uuid.uuid4().hex


def _set_persistent_cookies(response, user_id: str, **variants) -> None:
    """Attach sticky cookies so repeat visitors see the same variant."""
    response.set_cookie(
        USER_COOKIE, user_id, max_age=60 * 60 * 24 * 365, samesite="Lax"
    )
    for name, value in variants.items():
        if value is not None:
            response.set_cookie(
                name, value, max_age=60 * 60 * 24 * 365, samesite="Lax"
            )


# ---------------------------------------------------------------------------
# Routes — Experiment 1: Discount / Offer
# ---------------------------------------------------------------------------


@app.route("/")
def home():
    """Landing / discount A/B test page."""
    user_id = _resolve_user_id()
    variant = _resolve_variant(DISCOUNT_COOKIE)

    log_event(user_id, "discount", variant, "impression")

    template_vars = {
        "variant": variant,
        "headline": "Join & Get 10% Off" if variant == "B" else "Join Our Newsletter",
        "subheadline": (
            "Subscribe today and we'll email you a coupon for 10% off your "
            "first order — plus weekly tips, new arrivals, and subscriber-only "
            "deals."
            if variant == "B"
            else "Subscribe today for weekly tips, new arrivals, and insider "
            "updates delivered straight to your inbox."
        ),
        "cta_label": "Claim 10% Off" if variant == "B" else "Subscribe",
        "badge": "LIMITED TIME OFFER" if variant == "B" else "NEWSLETTER",
        "show_discount_ribbon": variant == "B",
    }

    response = make_response(render_template("home.html", **template_vars))
    _set_persistent_cookies(response, user_id, **{DISCOUNT_COOKIE: variant})
    return response


@app.route("/subscribe", methods=["POST"])
def subscribe():
    """Handle the newsletter subscription submission (discount experiment)."""
    user_id = _resolve_user_id()
    variant = _resolve_variant(DISCOUNT_COOKIE)

    email = request.form.get("email", "").strip()
    if not email or "@" not in email:
        return (
            jsonify({"ok": False, "error": "Please enter a valid email address."}),
            400,
        )

    log_event(
        user_id,
        "discount",
        variant,
        "conversion",
        payload=f"email={email}",
    )

    response = make_response(
        redirect(url_for("thank_you", experiment="discount", variant=variant))
    )
    _set_persistent_cookies(response, user_id, **{DISCOUNT_COOKIE: variant})
    return response


# ---------------------------------------------------------------------------
# Routes — Experiment 2: Form Length
# ---------------------------------------------------------------------------


@app.route("/signup")
def signup():
    """Registration / form length A/B test page."""
    user_id = _resolve_user_id()
    variant = _resolve_variant(FORM_COOKIE)

    log_event(user_id, "form_length", variant, "impression")

    response = make_response(
        render_template("signup.html", variant=variant)
    )
    _set_persistent_cookies(response, user_id, **{FORM_COOKIE: variant})
    return response


@app.route("/register", methods=["POST"])
def register():
    """Handle the registration submission (form length experiment)."""
    user_id = _resolve_user_id()
    variant = _resolve_variant(FORM_COOKIE)

    email = request.form.get("email", "").strip()
    if not email or "@" not in email:
        return (
            jsonify({"ok": False, "error": "Please enter a valid email address."}),
            400,
        )

    if variant == "B":
        name = request.form.get("name", "").strip()
        school = request.form.get("school", "").strip()
        if not name or not school:
            return (
                jsonify(
                    {"ok": False, "error": "Please fill in every required field."}
                ),
                400,
            )
        payload = f"email={email}; name={name}; school={school}"
    else:
        payload = f"email={email}"

    log_event(user_id, "form_length", variant, "conversion", payload=payload)

    response = make_response(
        redirect(url_for("thank_you", experiment="form_length", variant=variant))
    )
    _set_persistent_cookies(response, user_id, **{FORM_COOKIE: variant})
    return response


# ---------------------------------------------------------------------------
# Misc routes
# ---------------------------------------------------------------------------


@app.route("/thanks")
def thank_you():
    experiment = request.args.get("experiment", "")
    variant = request.args.get("variant", "")
    return render_template(
        "thanks.html", experiment=experiment, variant=variant
    )


@app.route("/stats")
def stats():
    """
    Live dashboard showing impressions, conversions, and rates for
    each experiment/variant pair.
    """
    db = get_db()
    rows = db.execute(
        """
        SELECT experiment,
               variant,
               SUM(event_type = 'impression') AS impressions,
               SUM(event_type = 'conversion') AS conversions
          FROM events
         GROUP BY experiment, variant
         ORDER BY experiment, variant
        """
    ).fetchall()

    results = []
    for r in rows:
        imp = r["impressions"] or 0
        conv = r["conversions"] or 0
        rate = (conv / imp) if imp else 0.0
        results.append(
            {
                "experiment": r["experiment"],
                "variant": r["variant"],
                "impressions": imp,
                "conversions": conv,
                "rate": rate,
            }
        )

    return render_template("stats.html", results=results)


@app.route("/healthz")
def healthz():
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    init_db()
    app.run(
        host=os.environ.get("HOST", "0.0.0.0"),
        port=int(os.environ.get("PORT", "5000")),
        debug=bool(os.environ.get("FLASK_DEBUG")),
    )
