"""
Simulate synthetic A/B-test data directly in the SQLite event log.

Useful for development, demo, and to sanity-check the analysis pipeline
when few real users have interacted with the app yet.

Each simulated user sees **one** experiment (discount OR form_length),
is randomly assigned to A or B, always records an impression, and then
converts with a pre-configured probability.  The resulting database is
fully compatible with ``analysis.py`` and the ``/stats`` dashboard.

Example
-------
    python simulate.py --n 2000 --seed 7
    python simulate.py --reset --n 5000

By default, the "true" conversion rates are:

    discount     A = 0.10   B = 0.15       (B wins, +5 pp)
    form_length  A = 0.50   B = 0.35       (A wins, +15 pp)

so that the analysis script can demonstrate both a winning and losing
variant.  Override them with --discount-a / --discount-b / --form-a /
--form-b.
"""

from __future__ import annotations

import argparse
import os
import random
import sqlite3
import uuid
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path

from flask_app import DB_PATH as DEFAULT_DB_PATH, SCHEMA


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    conn.commit()


def reset_events(conn: sqlite3.Connection) -> None:
    conn.execute("DELETE FROM events")
    conn.commit()


def simulate(
    db_path: Path,
    n_users: int,
    *,
    discount_rates: tuple[float, float],
    form_rates: tuple[float, float],
    seed: int = 0,
    reset: bool = False,
) -> None:
    random.seed(seed)

    db_path.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(db_path)) as conn:
        ensure_schema(conn)
        if reset:
            reset_events(conn)

        rows_to_insert = []
        now = datetime.now(timezone.utc)

        for i in range(n_users):
            uid = uuid.uuid4().hex
            experiment = random.choice(["discount", "form_length"])
            variant = random.choice(["A", "B"])

            if experiment == "discount":
                p_convert = discount_rates[0 if variant == "A" else 1]
            else:
                p_convert = form_rates[0 if variant == "A" else 1]

            ts_imp = (now - timedelta(seconds=n_users - i)).isoformat(
                timespec="seconds"
            )

            rows_to_insert.append(
                (
                    uid,
                    experiment,
                    variant,
                    "impression",
                    ts_imp,
                    "Simulator/1.0",
                    "",
                    None,
                )
            )

            if random.random() < p_convert:
                ts_conv = (
                    now
                    - timedelta(seconds=n_users - i)
                    + timedelta(seconds=random.randint(5, 120))
                ).isoformat(timespec="seconds")
                rows_to_insert.append(
                    (
                        uid,
                        experiment,
                        variant,
                        "conversion",
                        ts_conv,
                        "Simulator/1.0",
                        "",
                        "simulated=1",
                    )
                )

        conn.executemany(
            """
            INSERT INTO events
                (user_id, experiment, variant, event_type,
                 created_at, user_agent, referrer, payload)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows_to_insert,
        )
        conn.commit()

        total_events = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]

    print(
        f"Simulated {n_users} users → wrote {len(rows_to_insert):,} events "
        f"to {db_path} (total events now: {total_events:,})."
    )


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--db",
        type=Path,
        default=Path(os.environ.get("AB_DB_PATH", str(DEFAULT_DB_PATH))),
        help="Path to the SQLite database (default: ab_test.db).",
    )
    p.add_argument("--n", type=int, default=2000, help="Number of users to simulate.")
    p.add_argument("--seed", type=int, default=42, help="Random seed.")
    p.add_argument(
        "--reset",
        action="store_true",
        help="Delete all existing events before simulating.",
    )
    p.add_argument("--discount-a", type=float, default=0.10)
    p.add_argument("--discount-b", type=float, default=0.15)
    p.add_argument("--form-a", type=float, default=0.50)
    p.add_argument("--form-b", type=float, default=0.35)
    args = p.parse_args(argv)

    simulate(
        args.db,
        args.n,
        discount_rates=(args.discount_a, args.discount_b),
        form_rates=(args.form_a, args.form_b),
        seed=args.seed,
        reset=args.reset,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
