# 5243 Project 3 — Designing and Conducting an A/B Test

Two interchangeable implementations of the same A/B-testing website are
included in this repo:

| Implementation         | Location        | Entrypoint     | Typical host            |
|------------------------|-----------------|----------------|--------------------------|
| **R Shiny** (easiest to deploy) | `r_app/`        | `app.R`        | shinyapps.io (R Shiny)   |
| Shiny for Python       | repo root       | `app.py`       | shinyapps.io (Python)    |
| Flask (optional)       | repo root       | `flask_app.py` | Render / Heroku / Fly    |

All three share the same SQLite schema, so `analysis.R` / `analysis.py`
and `simulate.R` / `simulate.py` are drop-in equivalents.

> **Just want a URL as fast as possible?** Follow `r_app/README.md`.
> The R Shiny version deploys to shinyapps.io in two commands.

---

A web application and analysis pipeline for the two A/B-testing
experiments described in the project brief:

| # | Experiment            | Variant A                      | Variant B                                  | Metric             |
|---|-----------------------|--------------------------------|--------------------------------------------|--------------------|
| 1 | **Discount / Offer**  | "Join Our Newsletter"          | "Join & Get 10 % Off"                      | Conversion rate    |
| 2 | **Form Length**       | Short form (email only)        | Long form (name + email + school)          | Submission rate    |

Both experiments live in the same Shiny app as separate tabs:

* **Newsletter** tab — Experiment 1 (discount/offer).
* **Register** tab — Experiment 2 (form length).
* **Live stats** tab — real-time impressions / conversions dashboard.

Users are **randomly assigned** to a variant on session start. A variant
can be forced via a query string (`?discount=A|B`, `?form=A|B`, or the
legacy `?group=A|B` which sets both) — useful for sharing a specific
version with classmates.

All impressions and conversions are appended to a local **SQLite**
database (`ab_test.db`). A separate script (`analysis.py`) reads that
database and runs statistical tests (two-proportion z-test, Pearson
chi-squared, 95 % Wilson confidence intervals, bootstrap CI for relative
lift).

> **Note**
> A Flask implementation (`flask_app.py`, `wsgi.py`, `Procfile`,
> `Dockerfile`, `render.yaml`) is still included as an alternative
> deployment target. It writes to the same SQLite schema, so the analysis
> pipeline works against either backend.

---

## 1. Project layout

```
.
├── app.py                  # Shiny for Python app (canonical entrypoint)
├── flask_app.py            # Alternative Flask implementation
├── wsgi.py                 # gunicorn entry point for the Flask version
├── analysis.py             # Offline statistical analysis
├── simulate.py             # Synthetic event generator
├── requirements.txt        # Python dependencies (shiny, Flask, stats stack)
├── manifest.json           # rsconnect-python deployment manifest (shinyapps.io)
├── pyproject.toml          # Pins requires-python for rsconnect
├── .python-version         # Pins Python 3.12
├── Procfile                # Buildpack start command (Flask variant)
├── render.yaml             # Render blueprint (Flask variant)
├── Dockerfile              # Container image (Flask variant)
├── deploy_shinyapps.sh     # One-command shinyapps.io deploy helper
├── templates/              # Jinja2 HTML templates used by the Flask version
├── static/                 # CSS for the Flask templates
└── reports/                # Created by analysis.py — plots & summary.csv
```

---

## 2. Quick start

### 2.1 Install

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2.2 Run the Shiny app locally

```bash
shiny run --reload app.py
# or
python -m shiny run --reload app.py
```

Open <http://127.0.0.1:8000> (Shiny's default port). Every tab visit
writes an impression event; every successful submission writes a
conversion event, both to `ab_test.db`.

Environment variables:

| Variable       | Purpose                                   | Default      |
|----------------|-------------------------------------------|--------------|
| `AB_DB_PATH`   | Path to the SQLite event log              | `ab_test.db` |

### 2.3 Simulate data (optional)

```bash
python simulate.py --n 2000 --reset
```

### 2.4 Run the analysis

```bash
python analysis.py --db ab_test.db --out reports/
```

You will see per-variant counts, Wilson confidence intervals, two-
proportion z-test, Pearson chi-squared, and bootstrap relative-lift CIs
for each experiment. PNG charts are saved under `reports/`.

---

## 3. Deploying to **shinyapps.io**

Shiny for Python apps deploy in two commands using `rsconnect-python`.

```bash
pip install rsconnect-python                # one-time

# Grab your token/secret from https://www.shinyapps.io/admin/#/tokens
rsconnect add \
    --account <YOUR-ACCOUNT> \
    --name shinyapps \
    --token <TOKEN> \
    --secret <SECRET>

rsconnect deploy shiny . \
    --name shinyapps \
    --title "A/B Test Experiment — Lumen Labs"
```

Or, as a one-liner once `rsconnect add` has been run:

```bash
./deploy_shinyapps.sh
```

`manifest.json` in the repo pins `entrypoint=app`, Python 3.12, and the
dependencies from `requirements.txt`, so no further configuration is
needed. In ~2 minutes you get a public URL like
`https://<account>.shinyapps.io/ab-test-experiment-lumen-labs/` that you
can share with classmates to collect data.

**Sharing links to force variants** (handy for balanced assignment while
the sample is small):

```
https://.../?discount=A
https://.../?discount=B
https://.../?form=A
https://.../?form=B
https://.../?group=A              # legacy — sets both experiments
```

> **Note on SQLite persistence**
> shinyapps.io restarts idle instances, which can reset `ab_test.db`.
> For a short-running class experiment this is fine (everyone hits the
> app while it's warm). For longer collections, either deploy to Render
> using `render.yaml` (which provisions a persistent disk) or point
> `AB_DB_PATH` at a mounted volume.

---

## 4. Alternative deployment (Flask)

If you prefer a traditional WSGI server, the Flask implementation in
`flask_app.py` is still there:

```bash
gunicorn wsgi:app --bind 0.0.0.0:8000
```

Available hosts:

* **Render** — one-click via `render.yaml` (provisions a persistent disk).
* **Railway / Heroku** — auto-detects the `Procfile`.
* **Fly.io / any container host** — uses the included `Dockerfile`.

---

## 5. Experimental design

### 5.1 Research questions

1. **Discount / Offer** — Does presenting a 10 %-off coupon on the
   newsletter landing page increase email sign-up conversion compared to a
   standard "Join our newsletter" call-to-action?
2. **Form Length** — Does reducing a registration form from three fields
   (name + email + school) to a single field (email) increase the
   registration-submission rate?

### 5.2 Hypotheses

For both experiments, we test

* **H₀**: `p_A = p_B` — the variant has no effect on the conversion rate.
* **H₁**: `p_A ≠ p_B` — the variant changes the conversion rate.

Two-sided test, α = 0.05.

### 5.3 Randomisation

* Each Shiny session gets an unbiased 50/50 assignment
  (`random.choice(["A","B"])`) independently for each experiment.
* `?discount=A|B`, `?form=A|B`, or `?group=A|B` overrides the assignment —
  use these for targeted share links, but **not** when collecting primary
  analysis data (they break randomisation).

### 5.4 Metrics

| Experiment    | Metric                                | Definition                                                              |
|---------------|---------------------------------------|-------------------------------------------------------------------------|
| Discount      | Newsletter conversion rate            | `# subscribe submissions / # Newsletter-tab impressions`                |
| Form length   | Registration submission rate          | `# completed registrations / # Register-tab impressions`                |

### 5.5 Sample size (α = 0.05, power = 0.80)

| Experiment    | Baseline | MDE      | Required n / arm |
|---------------|----------|----------|------------------|
| Discount      | 10 %     | +5 pp    | ≈ 680            |
| Form length   | 50 %     | ±10 pp   | ≈ 390            |

---

## 6. Statistical analysis

`analysis.py` performs, for each experiment:

1. **Per-variant summaries** — impressions, conversions, rate, 95 %
   Wilson confidence interval.
2. **Two-proportion z-test** (two-sided).
3. **Pearson chi-squared** on the 2×2 contingency table.
4. **Effect size** — absolute (pp) and relative lift of B vs A.
5. **Bootstrap 95 % CI for the relative lift** — 20 000 paired binomial
   resamples.
6. **Plot** — bar chart of the two rates with Wilson error bars.

---

## 7. Reproducing the included example results

```bash
python simulate.py --n 4000 --seed 7 --reset
python analysis.py --out reports/
```

---

## 8. Troubleshooting

* **"Database not found"** — run the app at least once, or
  `python simulate.py --n 1 --reset`.
* **Everyone keeps seeing the same variant** — each browser session gets
  an independent random assignment, and forcing `?discount=…` or
  `?form=…` pins it. Open a new tab / private window for a fresh
  random assignment.
* **Shiny app won't start** — make sure you're on Python ≥ 3.11 and
  `pip install -r requirements.txt` succeeded; `shiny` needs compiled
  wheels for a few transitive deps on older Python.
