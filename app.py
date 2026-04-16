"""
A/B Test Shiny for Python App
=============================

Implements the two experiments described in the project brief, built with
Shiny for Python (https://shiny.posit.co/py) and deployable to
shinyapps.io with a single ``rsconnect deploy shiny`` command.

Experiment 1 — Discount / Offer Page  (Newsletter tab)
    * Variant A: "Join Our Newsletter"           (no discount)
    * Variant B: "Join & Get 10% Off"            (discount incentive)
    * Metric:    newsletter conversion rate

Experiment 2 — Form Length Test       (Register tab)
    * Variant A: email only
    * Variant B: name + email + school
    * Metric:    registration submission rate

Randomisation
-------------
Every Shiny session gets a fresh 50/50 assignment for each experiment on
connect, or the assignment encoded in the URL query string (``?discount=A``,
``?form=B``, or the legacy ``?group=A|B`` which sets both).

Data
----
All impressions and conversions are appended to the same SQLite event log
used by the Flask version (``ab_test.db``), so ``analysis.py`` and
``simulate.py`` work unchanged.  On read-only hosts (e.g. shinyapps.io
free plan restarts), set ``AB_DB_PATH=/tmp/ab_test.db``.

Running locally
---------------
    shiny run --reload app.py              # http://localhost:8000
    # or:
    python -m shiny run --reload app.py

Deploying to shinyapps.io
-------------------------
    pip install rsconnect-python
    rsconnect add --account <ACCOUNT> --name <NAME> --token <TOKEN> --secret <SECRET>
    rsconnect deploy shiny . --name <NAME> --title "A/B Test Experiment"
"""

from __future__ import annotations

import os
import random
import sqlite3
import uuid
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs

import pandas as pd
from shiny import App, Inputs, Outputs, Session, reactive, render, ui

# ---------------------------------------------------------------------------
# Configuration / database
# ---------------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = Path(os.environ.get("AB_DB_PATH", BASE_DIR / "ab_test.db"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         TEXT    NOT NULL,
    experiment      TEXT    NOT NULL,
    variant         TEXT    NOT NULL,
    event_type      TEXT    NOT NULL,
    created_at      TEXT    NOT NULL,
    user_agent      TEXT,
    referrer        TEXT,
    payload         TEXT
);
CREATE INDEX IF NOT EXISTS idx_events_experiment_variant
    ON events (experiment, variant, event_type);
"""


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(DB_PATH)) as conn:
        conn.executescript(SCHEMA)
        conn.commit()


def log_event(
    user_id: str,
    experiment: str,
    variant: str,
    event_type: str,
    *,
    user_agent: str = "",
    referrer: str = "",
    payload: str | None = None,
) -> None:
    with closing(sqlite3.connect(DB_PATH)) as conn:
        conn.execute(
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
                user_agent,
                referrer,
                payload,
            ),
        )
        conn.commit()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def parse_query(search: str | None) -> dict[str, str]:
    """Parse a ``?foo=bar`` style query string into a lowercase-key dict."""
    if not search:
        return {}
    qs = search.lstrip("?")
    parsed = parse_qs(qs, keep_blank_values=True)
    return {k.lower(): (v[0] if v else "") for k, v in parsed.items()}


def resolve_variant(q: dict[str, str], key: str) -> str:
    """Return variant from URL (``?<key>=A|B`` or legacy ``?group=``)."""
    for candidate in (key, "group"):
        val = q.get(candidate, "").upper().strip()
        if val in {"A", "B"}:
            return val
    return random.choice(["A", "B"])


# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------

_STYLES = ui.tags.style(
    """
    :root {
      --primary: #5b6cff;
      --accent:  #ff7a59;
      --ink:     #0f172a;
      --ink-soft:#475569;
      --border:  #e2e8f0;
      --surface: #ffffff;
      --bg:      #f9fafc;
    }
    body { background: linear-gradient(180deg,#f9fafc 0%,#eef2ff 100%); }

    .navbar { background: #fff !important; border-bottom:1px solid var(--border); }
    .navbar-brand { font-weight:800; letter-spacing:-0.02em; }

    .hero-card {
      max-width: 680px; margin: 2.5rem auto; padding: 2.5rem;
      background: #fff; border-radius: 14px;
      border: 1px solid var(--border);
      box-shadow: 0 20px 60px rgba(15,23,42,.08);
      text-align: center;
    }
    .badge-pill {
      display:inline-block; padding:.35rem .9rem; border-radius:999px;
      background: rgba(91,108,255,.12); color: var(--primary);
      font-size:.78rem; font-weight:700; letter-spacing:.12em;
      text-transform:uppercase;
    }
    .badge-pill.offer { background: rgba(255,122,89,.15); color: var(--accent); }
    h1.hero-title { font-size: clamp(1.9rem,4vw,2.8rem); font-weight:800;
                    letter-spacing:-0.03em; margin: 1rem 0 .75rem; }
    .ribbon {
      display:inline-block; padding:.15rem .6rem; margin-left:.4rem;
      background: var(--accent); color:#1a0d07; font-weight:800;
      border-radius: 8px; transform: rotate(-3deg); font-size:.85rem;
    }
    .hero-sub { color: var(--ink-soft); font-size:1.05rem; line-height:1.55; }

    .cta-btn { width: 100%; padding:.9rem 1.2rem; border:none; cursor:pointer;
               background: var(--primary); color:#fff; font-weight:700;
               border-radius: 999px; font-size:1rem;
               transition: transform .12s, box-shadow .12s, background .2s; }
    .cta-btn:hover { transform: translateY(-1px);
                     box-shadow: 0 10px 24px rgba(91,108,255,.35); }
    .cta-btn.offer { background: var(--accent); color:#1a0d07; }

    input.form-control, .form-control {
      padding: .85rem 1rem !important; border-radius:10px !important;
      border:1px solid var(--border) !important; font-size:1rem !important;
    }
    label.control-label { font-weight:600; color:var(--ink); }
    .fine-print { color:var(--ink-soft); font-size:.85rem; margin-top:1rem; }

    .stats-card { background:#fff; border:1px solid var(--border);
                  border-radius:14px; padding:1.5rem; margin:1rem 0;
                  box-shadow: 0 2px 8px rgba(15,23,42,.06); }
    .stats-card table { width:100%; border-collapse: collapse; }
    .stats-card th,.stats-card td { padding:.6rem .75rem; text-align:left;
                                    border-bottom:1px solid var(--border); }
    .stats-card th { background:#f5f7fb; color:var(--ink-soft);
                     font-size:.82rem; letter-spacing:.08em;
                     text-transform:uppercase; }

    .variant-tag { display:inline-block; padding:.1rem .55rem;
                   border-radius:6px; background:#eef2ff; color:var(--primary);
                   font-size:.75rem; font-weight:700; letter-spacing:.1em; }

    .thanks { color: #059669; font-weight:600; }
    .error  { color: #b91c1c; font-weight:600; }
    """
)


def _newsletter_panel() -> Any:
    return ui.nav_panel(
        "Newsletter",
        ui.div(
            ui.output_ui("newsletter_ui"),
            class_="container",
        ),
    )


def _register_panel() -> Any:
    return ui.nav_panel(
        "Register",
        ui.div(
            ui.output_ui("register_ui"),
            class_="container",
        ),
    )


def _stats_panel() -> Any:
    return ui.nav_panel(
        "Live stats",
        ui.div(
            ui.h2("Live experiment stats"),
            ui.p(
                "Real-time impressions and conversions per experiment / "
                "variant. Run ",
                ui.tags.code("python analysis.py"),
                " for full statistical inference.",
                class_="fine-print",
            ),
            ui.output_ui("stats_ui"),
            class_="container",
            style="max-width:860px; margin:2rem auto;",
        ),
    )


app_ui = ui.page_navbar(
    _newsletter_panel(),
    _register_panel(),
    _stats_panel(),
    title="Lumen Labs",
    id="nav",
    header=ui.tags.head(
        ui.tags.meta(charset="utf-8"),
        ui.tags.meta(
            name="viewport", content="width=device-width, initial-scale=1"
        ),
        _STYLES,
    ),
    footer=ui.tags.footer(
        ui.p(
            "A/B-testing class project · Share ",
            ui.tags.code("?discount=A"),
            " / ",
            ui.tags.code("?discount=B"),
            " / ",
            ui.tags.code("?form=A"),
            " / ",
            ui.tags.code("?form=B"),
            " to force a variant.",
            class_="fine-print",
            style="text-align:center; padding:1.5rem;",
        ),
    ),
)


# ---------------------------------------------------------------------------
# Server
# ---------------------------------------------------------------------------

def server(input: Inputs, output: Outputs, session: Session) -> None:
    init_db()

    # Per-session identity + variant assignment ---------------------------

    # Start with a random 50/50 assignment.  Once the client reports its
    # URL (via Shiny's hidden ``.clientdata_url_search`` input), we
    # override the assignment if the visitor explicitly picked a variant
    # with ``?discount=A|B``, ``?form=A|B``, or the legacy ``?group=A|B``.

    user_id = reactive.Value(uuid.uuid4().hex)
    variant_discount = reactive.Value(random.choice(["A", "B"]))
    variant_form = reactive.Value(random.choice(["A", "B"]))

    @reactive.effect
    def _apply_url_override() -> None:
        try:
            search = input[".clientdata_url_search"]()
        except Exception:
            return
        q = parse_query(search)
        if any(k in q for k in ("discount", "group")):
            variant_discount.set(resolve_variant(q, "discount"))
        if any(k in q for k in ("form", "group")):
            variant_form.set(resolve_variant(q, "form"))

    # Track whether we've already recorded an impression for each tab
    # during this session, so switching tabs back and forth does not
    # inflate the impression count.
    _impressed = {"discount": reactive.Value(False), "form_length": reactive.Value(False)}

    def _user_agent() -> str:
        try:
            return session.http_conn.headers.get("user-agent", "")
        except Exception:
            return ""

    def _log_impression(experiment: str, variant: str) -> None:
        if _impressed[experiment]():
            return
        _impressed[experiment].set(True)
        log_event(
            user_id(),
            experiment,
            variant,
            "impression",
            user_agent=_user_agent(),
        )

    # The Newsletter tab is the default landing view, so record its
    # impression as soon as the session is established.
    @reactive.effect
    def _impression_on_tab_change() -> None:
        tab = input.nav()
        if tab == "Newsletter":
            _log_impression("discount", variant_discount())
        elif tab == "Register":
            _log_impression("form_length", variant_form())

    # ------------------------------------------------------------------ UI

    thanks_msg_1 = reactive.Value("")
    thanks_msg_2 = reactive.Value("")

    @output
    @render.ui
    def newsletter_ui():
        v = variant_discount()
        is_b = v == "B"
        headline = "Join & Get 10% Off" if is_b else "Join Our Newsletter"
        subhead = (
            "Subscribe today and we'll email you a coupon for 10% off "
            "your first order — plus weekly tips, new arrivals, and "
            "subscriber-only deals."
            if is_b
            else "Subscribe today for weekly tips, new arrivals, and "
            "insider updates delivered straight to your inbox."
        )
        badge_text = "Limited time offer" if is_b else "Newsletter"
        cta_label = "Claim 10% Off" if is_b else "Subscribe"

        hero_title = (
            ui.h1(
                headline,
                ui.tags.span("10% OFF", class_="ribbon") if is_b else "",
                class_="hero-title",
            )
        )

        feedback = thanks_msg_1()
        feedback_el = (
            ui.p(feedback, class_="thanks" if feedback.startswith("✓") else "error")
            if feedback
            else ""
        )

        return ui.div(
            ui.span(
                badge_text,
                class_="badge-pill" + (" offer" if is_b else ""),
            ),
            hero_title,
            ui.p(subhead, class_="hero-sub"),
            ui.input_text(
                "newsletter_email",
                label=None,
                placeholder="you@example.com",
                width="100%",
            ),
            ui.input_action_button(
                "subscribe_btn",
                cta_label,
                class_="cta-btn" + (" offer" if is_b else ""),
            ),
            feedback_el,
            ui.p(
                "Your variant: ",
                ui.tags.span(v, class_="variant-tag"),
                class_="fine-print",
            ),
            class_="hero-card",
        )

    @output
    @render.ui
    def register_ui():
        v = variant_form()
        show_extra = v == "B"

        feedback = thanks_msg_2()
        feedback_el = (
            ui.p(feedback, class_="thanks" if feedback.startswith("✓") else "error")
            if feedback
            else ""
        )

        extra_fields = (
            [
                ui.input_text(
                    "register_name",
                    "Full name",
                    placeholder="Ada Lovelace",
                    width="100%",
                ),
            ]
            if show_extra
            else []
        )
        extra_tail = (
            [
                ui.input_text(
                    "register_school",
                    "School",
                    placeholder="Columbia University",
                    width="100%",
                ),
            ]
            if show_extra
            else []
        )

        return ui.div(
            ui.h1("Create your free account", class_="hero-title"),
            ui.p(
                "Join thousands of students using Lumen Labs to track study "
                "progress and connect with classmates.",
                class_="hero-sub",
            ),
            *extra_fields,
            ui.input_text(
                "register_email",
                "Email address",
                placeholder="you@example.com",
                width="100%",
            ),
            *extra_tail,
            ui.input_action_button(
                "register_btn",
                "Create my account",
                class_="cta-btn",
            ),
            feedback_el,
            ui.p(
                "Your variant: ",
                ui.tags.span(v, class_="variant-tag"),
                class_="fine-print",
            ),
            class_="hero-card",
        )

    @output
    @render.ui
    def stats_ui():
        # Read fresh counts on each invalidation.
        stats_trigger()  # reactive dependency
        with closing(sqlite3.connect(DB_PATH)) as conn:
            rows = conn.execute(
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

        if not rows:
            return ui.p(
                "No events yet — interact with the Newsletter / Register tabs "
                "to generate data.",
                class_="fine-print",
            )

        by_exp: dict[str, list[dict[str, Any]]] = {}
        for exp, var, imp, conv in rows:
            imp = imp or 0
            conv = conv or 0
            rate = (conv / imp) if imp else 0.0
            by_exp.setdefault(exp, []).append(
                {
                    "variant": var,
                    "impressions": imp,
                    "conversions": conv,
                    "rate": rate,
                }
            )

        cards = []
        for exp, data in by_exp.items():
            header = ui.h3(exp.replace("_", " ").title())
            header_row = ui.tags.tr(
                ui.tags.th("Variant"),
                ui.tags.th("Impressions"),
                ui.tags.th("Conversions"),
                ui.tags.th("Rate"),
            )
            body = [
                ui.tags.tr(
                    ui.tags.td(ui.tags.strong(d["variant"])),
                    ui.tags.td(str(d["impressions"])),
                    ui.tags.td(str(d["conversions"])),
                    ui.tags.td(f"{d['rate'] * 100:.2f}%"),
                )
                for d in data
            ]
            cards.append(
                ui.div(
                    header,
                    ui.tags.table(
                        ui.tags.thead(header_row),
                        ui.tags.tbody(*body),
                    ),
                    class_="stats-card",
                )
            )
        return ui.div(*cards)

    # Auto-refresh the stats tab once per 5 seconds so multiple clients
    # see near-live counts without a manual reload.
    stats_trigger = reactive.Value(0)

    @reactive.effect
    def _tick_stats() -> None:
        reactive.invalidate_later(5.0)
        stats_trigger.set(stats_trigger() + 1)

    # --------------------------------------------------- event handlers

    @reactive.effect
    @reactive.event(input.subscribe_btn)
    def _handle_subscribe() -> None:
        email = (input.newsletter_email() or "").strip()
        if not email or "@" not in email:
            thanks_msg_1.set("Please enter a valid email address.")
            return
        v = variant_discount()
        log_event(
            user_id(),
            "discount",
            v,
            "conversion",
            user_agent=_user_agent(),
            payload=f"email={email}",
        )
        if v == "B":
            thanks_msg_1.set(
                "✓ Subscribed! Your 10% off coupon is on its way to "
                f"{email}."
            )
        else:
            thanks_msg_1.set(f"✓ Subscribed! Thanks — welcome to Lumen Labs.")
        stats_trigger.set(stats_trigger() + 1)

    @reactive.effect
    @reactive.event(input.register_btn)
    def _handle_register() -> None:
        email = (input.register_email() or "").strip()
        if not email or "@" not in email:
            thanks_msg_2.set("Please enter a valid email address.")
            return
        v = variant_form()
        if v == "B":
            try:
                name = (input.register_name() or "").strip()
            except Exception:
                name = ""
            try:
                school = (input.register_school() or "").strip()
            except Exception:
                school = ""
            if not name or not school:
                thanks_msg_2.set("Please fill in every required field.")
                return
            payload = f"email={email}; name={name}; school={school}"
        else:
            payload = f"email={email}"

        log_event(
            user_id(),
            "form_length",
            v,
            "conversion",
            user_agent=_user_agent(),
            payload=payload,
        )
        thanks_msg_2.set("✓ Account created — welcome to Lumen Labs!")
        stats_trigger.set(stats_trigger() + 1)


# ---------------------------------------------------------------------------

app = App(app_ui, server)
