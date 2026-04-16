"""
Statistical analysis for the A/B-test project.

Reads the SQLite event log produced by the Flask app (``ab_test.db``) and
produces, for every experiment:

    * Per-variant impression counts, conversion counts, and conversion rates.
    * 95 % Wilson confidence intervals for each conversion rate.
    * A two-proportion z-test comparing Variant A and Variant B.
    * A Pearson chi-squared test on the 2×2 contingency table.
    * Absolute and relative lift (B vs A) with bootstrap 95 % CI.
    * A bar-chart PNG (``<experiment>_rates.png``) of the two rates.

Usage
-----
    python analysis.py
    python analysis.py --db path/to/ab_test.db --out reports/

The script has no side effects on the database.
"""

from __future__ import annotations

import argparse
import math
import os
import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats
from statsmodels.stats.proportion import (
    proportion_confint,
    proportions_ztest,
)

try:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    HAS_MPL = True
except Exception:  # pragma: no cover — plotting is optional
    HAS_MPL = False


# ---------------------------------------------------------------------------

@dataclass
class VariantResult:
    variant: str
    impressions: int
    conversions: int

    @property
    def rate(self) -> float:
        return self.conversions / self.impressions if self.impressions else 0.0

    def wilson_ci(self, alpha: float = 0.05) -> tuple[float, float]:
        if self.impressions == 0:
            return (0.0, 0.0)
        lo, hi = proportion_confint(
            count=self.conversions,
            nobs=self.impressions,
            alpha=alpha,
            method="wilson",
        )
        return float(lo), float(hi)


# ---------------------------------------------------------------------------

def load_events(db_path: Path) -> pd.DataFrame:
    """Load the entire events table into a DataFrame."""
    if not db_path.exists():
        raise FileNotFoundError(
            f"Database not found at {db_path!s}. "
            "Run the Flask app (or simulate.py) to generate data first."
        )
    with sqlite3.connect(db_path) as conn:
        return pd.read_sql_query("SELECT * FROM events", conn)


def aggregate(df: pd.DataFrame) -> pd.DataFrame:
    """Return per experiment/variant counts of impressions and conversions."""
    if df.empty:
        return pd.DataFrame(
            columns=["experiment", "variant", "impressions", "conversions"]
        )

    pivot = (
        df.pivot_table(
            index=["experiment", "variant"],
            columns="event_type",
            values="id",
            aggfunc="count",
            fill_value=0,
        )
        .reset_index()
    )
    for col in ("impression", "conversion"):
        if col not in pivot.columns:
            pivot[col] = 0

    pivot = pivot.rename(
        columns={"impression": "impressions", "conversion": "conversions"}
    )
    return pivot[["experiment", "variant", "impressions", "conversions"]]


# ---------------------------------------------------------------------------

def bootstrap_lift_ci(
    a: VariantResult, b: VariantResult, n_boot: int = 20_000, seed: int = 42
) -> tuple[float, float]:
    """Bootstrap a 95 % CI for the relative lift (B/A − 1)."""
    if a.impressions == 0 or b.impressions == 0 or a.rate == 0:
        return (float("nan"), float("nan"))

    rng = np.random.default_rng(seed)
    a_draws = rng.binomial(a.impressions, a.rate, size=n_boot) / a.impressions
    b_draws = rng.binomial(b.impressions, b.rate, size=n_boot) / b.impressions
    safe_a = np.where(a_draws == 0, np.nan, a_draws)
    lifts = (b_draws - safe_a) / safe_a
    lo, hi = np.nanpercentile(lifts, [2.5, 97.5])
    return float(lo), float(hi)


def analyse_experiment(
    name: str, rows: pd.DataFrame, out_dir: Path
) -> dict:
    """Run all statistical tests on a single experiment."""
    if rows.empty:
        print(f"[{name}] no data — skipping.")
        return {}

    variants = {
        r.variant: VariantResult(
            variant=r.variant,
            impressions=int(r.impressions),
            conversions=int(r.conversions),
        )
        for r in rows.itertuples(index=False)
    }

    print(f"\n=== Experiment: {name} ===")
    for v in sorted(variants):
        vr = variants[v]
        lo, hi = vr.wilson_ci()
        print(
            f"  Variant {v}: {vr.conversions:>5}/{vr.impressions:<5} "
            f"= {vr.rate:>6.2%}   95 % CI [{lo:.3f}, {hi:.3f}]"
        )

    if {"A", "B"}.issubset(variants):
        a, b = variants["A"], variants["B"]

        counts = np.array([b.conversions, a.conversions])
        nobs = np.array([b.impressions, a.impressions])
        z_stat, p_z = proportions_ztest(counts, nobs, alternative="two-sided")

        contingency = np.array(
            [
                [a.conversions, a.impressions - a.conversions],
                [b.conversions, b.impressions - b.conversions],
            ]
        )
        chi2, p_chi, dof, expected = stats.chi2_contingency(
            contingency, correction=False
        )

        abs_lift = b.rate - a.rate
        rel_lift = (b.rate - a.rate) / a.rate if a.rate else float("nan")
        boot_lo, boot_hi = bootstrap_lift_ci(a, b)

        print("\n  Two-proportion z-test (B vs A)")
        print(f"    z         = {z_stat:+.3f}")
        print(f"    p-value   = {p_z:.4f}")

        print("\n  Pearson chi-squared (1 dof)")
        print(f"    chi2      = {chi2:.3f}")
        print(f"    p-value   = {p_chi:.4f}")

        print("\n  Effect size")
        print(f"    Abs. lift = {abs_lift:+.4f} ({abs_lift * 100:+.2f} pp)")
        print(f"    Rel. lift = {rel_lift:+.2%}")
        print(
            f"    95 % bootstrap CI for rel. lift: "
            f"[{boot_lo:+.2%}, {boot_hi:+.2%}]"
        )

        verdict = (
            "Statistically significant at α = 0.05"
            if p_z < 0.05
            else "NOT statistically significant at α = 0.05"
        )
        print(f"\n  Verdict: {verdict}")

        if HAS_MPL:
            _plot(name, a, b, out_dir)

        return {
            "experiment": name,
            "A": a,
            "B": b,
            "z_stat": z_stat,
            "p_z": p_z,
            "chi2": chi2,
            "p_chi": p_chi,
            "abs_lift": abs_lift,
            "rel_lift": rel_lift,
            "boot_ci": (boot_lo, boot_hi),
        }

    print("  Only one variant has data — skipping inferential tests.")
    return {}


def _plot(name: str, a: VariantResult, b: VariantResult, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{name}_rates.png"

    labels = [f"A\n(n={a.impressions})", f"B\n(n={b.impressions})"]
    rates = [a.rate, b.rate]
    errs = np.array(
        [
            [a.rate - a.wilson_ci()[0], a.wilson_ci()[1] - a.rate],
            [b.rate - b.wilson_ci()[0], b.wilson_ci()[1] - b.rate],
        ]
    ).T

    fig, ax = plt.subplots(figsize=(5.2, 4))
    bars = ax.bar(
        labels,
        rates,
        yerr=errs,
        color=["#94a3b8", "#5b6cff"],
        capsize=8,
        edgecolor="#0f172a",
        linewidth=0.8,
    )
    ax.set_ylabel("Conversion rate")
    ax.set_title(f"{name} — conversion rate by variant\n(error bars = 95% Wilson CI)")
    ax.set_ylim(0, max(max(rates) * 1.4, 0.05))
    for bar, r in zip(bars, rates):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height(),
            f"{r:.1%}",
            ha="center",
            va="bottom",
            fontweight="bold",
        )
    plt.tight_layout()
    plt.savefig(path, dpi=150)
    plt.close(fig)
    print(f"  Plot saved to {path}")


# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--db",
        type=Path,
        default=Path(os.environ.get("AB_DB_PATH", "ab_test.db")),
        help="Path to the SQLite events database.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("reports"),
        help="Directory where plots / CSV summaries are written.",
    )
    args = parser.parse_args(argv)

    try:
        df = load_events(args.db)
    except FileNotFoundError as exc:
        print(exc, file=sys.stderr)
        return 2

    agg = aggregate(df)
    if agg.empty:
        print("No events in database yet.")
        return 0

    args.out.mkdir(parents=True, exist_ok=True)
    agg.to_csv(args.out / "summary.csv", index=False)

    for name, group in agg.groupby("experiment"):
        analyse_experiment(name, group, args.out)

    print(f"\nCSV summary written to {args.out / 'summary.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
