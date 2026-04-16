# 5243 Project 3 — Designing and Conducting an A/B Test

A self-contained **Flask** web application and analysis pipeline for two
A/B-testing experiments described in the project brief:

| # | Experiment            | Variant A                      | Variant B                                  | Metric             |
|---|-----------------------|--------------------------------|--------------------------------------------|--------------------|
| 1 | **Discount / Offer**  | "Join Our Newsletter"          | "Join & Get 10 % Off"                      | Conversion rate    |
| 2 | **Form Length**       | Short form (email only)        | Long form (name + email + school)          | Submission rate    |

Both experiments are live on the same site:

* `/`        — Landing page hosting **Experiment 1** (discount/offer).
* `/signup`  — Registration page hosting **Experiment 2** (form length).
* `/stats`   — Live impressions / conversions dashboard.

Users are **randomly assigned** to a variant on first visit. The assignment
is stored in a cookie so that the same user consistently sees the same
variant on repeat visits. You can also force a variant via a query string
(`?group=A` or `?group=B`) — useful for sharing a specific version.

All impressions and conversions are written to a local **SQLite** database
(`ab_test.db`). A separate script (`analysis.py`) reads that database and
runs statistical tests (two-proportion z-test, Pearson chi-squared,
95 % Wilson confidence intervals, bootstrap CI for relative lift).

---

## 1. Project layout

```
.
├── app.py              # Flask application (routes + cookie-based assignment + event logging)
├── analysis.py         # Offline statistical analysis of the SQLite event log
├── simulate.py         # Generate synthetic events for demo / sanity checks
├── requirements.txt    # Python dependencies
├── templates/          # Jinja2 HTML templates
│   ├── base.html
│   ├── home.html       # Discount experiment landing page
│   ├── signup.html     # Form-length experiment registration page
│   ├── thanks.html
│   └── stats.html
├── static/
│   └── styles.css      # Modern responsive CSS
└── reports/            # Created by analysis.py — plots & summary.csv
```

The SQLite database `ab_test.db` is created on first run and is excluded
from version control (see `.gitignore`).

---

## 2. Quick start

### 2.1 Install

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2.2 Run the web app

```bash
python app.py
```

The server starts at <http://localhost:5000>. Every visit creates an
impression event; every successful form submission creates a conversion
event, both logged to `ab_test.db`.

Environment variables you can set:

| Variable       | Purpose                                | Default      |
|----------------|----------------------------------------|--------------|
| `HOST`         | Bind address                           | `0.0.0.0`    |
| `PORT`         | Listen port                            | `5000`       |
| `AB_DB_PATH`   | Path to the SQLite database            | `ab_test.db` |
| `SECRET_KEY`   | Flask secret key                       | dev-only     |
| `FLASK_DEBUG`  | Set to a truthy value to enable debug  | unset        |

### 2.3 Simulate data (optional)

If you would like to see the analysis pipeline end-to-end without manually
submitting thousands of forms, generate synthetic events:

```bash
python simulate.py --n 2000 --reset       # reset db and simulate 2000 users
```

The simulator writes events that are indistinguishable from real ones
(except the `user_agent` field, which is `Simulator/1.0`).

### 2.4 Run the analysis

```bash
python analysis.py --db ab_test.db --out reports/
```

You will see per-variant counts, Wilson confidence intervals, two-proportion
z-test, Pearson chi-squared, and bootstrap relative-lift CIs for each
experiment. Plots are saved under `reports/`.

---

## 3. Experimental design

### 3.1 Research questions

1. **Discount / Offer** — Does presenting a 10 %-off coupon on the
   newsletter landing page increase email sign-up conversion compared to a
   standard "Join our newsletter" call-to-action?
2. **Form Length** — Does reducing a registration form from three fields
   (name + email + school) to a single field (email) increase the
   registration-submission rate?

### 3.2 Hypotheses

For both experiments, we test

* **H₀**: `p_A = p_B` — the variant has no effect on the conversion rate.
* **H₁**: `p_A ≠ p_B` — the variant changes the conversion rate.

We pre-register a significance level of **α = 0.05** and plan to run a
two-sided test because we are interested in the variant's impact in either
direction.

### 3.3 Randomization

* First-time visitors are assigned a variant with `random.choice(["A","B"])`
  — an unbiased 50/50 Bernoulli split.
* The assignment is stored in two cookies (`ab_discount_variant`,
  `ab_form_variant`) with a one-year TTL, keeping treatment assignment
  stable across sessions (sticky bucketing).
* A `?group=A|B` query string overrides the cookie/random assignment. This
  is useful to share a specific version on Discord/email but **should not
  be used** when collecting primary-analysis data because it breaks
  randomisation.

### 3.4 Metrics

| Experiment    | Metric                                | Definition                                                              |
|---------------|---------------------------------------|-------------------------------------------------------------------------|
| Discount      | Newsletter conversion rate            | `# subscribe submissions / # landing-page impressions`                  |
| Form length   | Registration submission rate          | `# completed registrations / # signup-page impressions`                 |

Both metrics are proportions, so the same statistical machinery applies.

### 3.5 Sample size

Using a two-sided two-proportion test with α = 0.05, power = 0.80:

| Experiment    | Expected baseline | Minimum detectable effect | Required n per arm |
|---------------|-------------------|---------------------------|--------------------|
| Discount      | 10 %              | +5 pp (→ 15 %)            | ≈ 680              |
| Form length   | 50 %              | ±10 pp                    | ≈ 390              |

See `analysis.py` for the formulas; totals are doubled to cover both arms.

---

## 4. Statistical analysis

`analysis.py` performs, for each experiment:

1. **Per-variant summaries** — impressions, conversions, rate, 95 % Wilson
   confidence interval (`statsmodels.stats.proportion.proportion_confint`).
2. **Two-proportion z-test** (`proportions_ztest`, two-sided).
3. **Pearson chi-squared** on the 2×2 contingency table
   (`scipy.stats.chi2_contingency`, no continuity correction).
4. **Effect size** — absolute (pp) and relative lift of B vs A.
5. **Bootstrap 95 % CI for the relative lift** — 20 000 paired binomial
   resamples.
6. **Plot** — bar chart of the two rates with Wilson error bars.

---

## 5. Sharing the experiment

To collect more data, share any of the following links:

* `https://YOUR-URL/` — landing page (both experiments reachable from nav).
* `https://YOUR-URL/?group=A` — force Variant A of the discount experiment.
* `https://YOUR-URL/?group=B` — force Variant B of the discount experiment.
* `https://YOUR-URL/signup?group=A` — short registration form.
* `https://YOUR-URL/signup?group=B` — long registration form.

**Tip**: for the primary analysis, share the un-parameterized URLs so that
the app performs an unbiased random assignment.

---

## 6. Reproducing the included example results

```bash
python simulate.py --n 4000 --seed 7 --reset    # ~4000 simulated users
python analysis.py --out reports/               # writes summary + plots
```

This seeds the database with synthetic events drawn from pre-configured
"true" rates (see `simulate.py`), then runs the full analysis — a quick
sanity check that the pipeline is wired correctly end-to-end.

---

## 7. Deployment

The repo ships with everything needed to deploy to a free host.
Production serving uses **gunicorn** (see `requirements.txt`, `Procfile`,
`wsgi.py`).

### 7.1 Render (one-click, recommended)

1. Push this branch to GitHub (already done).
2. Go to <https://dashboard.render.com/select-repo?type=web>, pick this
   repo, and Render will detect `render.yaml` automatically. Click
   **Apply** — it sets the build/start commands, mounts a 1 GB persistent
   disk at `/var/data`, and pins `AB_DB_PATH` so SQLite survives
   redeploys.
3. In ~2 minutes you get a URL like `https://ab-test-website.onrender.com`.

### 7.2 Railway

1. <https://railway.app> → **New Project → Deploy from GitHub repo**.
2. It auto-detects the `Procfile` and runs `gunicorn wsgi:app`.
3. Add a volume if you want SQLite persistence; otherwise the DB resets
   on each redeploy (fine for a short-running class experiment).

### 7.3 Fly.io

```bash
fly launch --no-deploy                       # accepts the included Dockerfile
fly volumes create ab_data --size 1          # optional, for DB persistence
fly deploy
```

### 7.4 Any Docker host

```bash
docker build -t ab-test-website .
docker run -p 8000:8000 -v $(pwd)/data:/data ab-test-website
# open http://localhost:8000
```

### 7.5 Quick public URL without deploying (ngrok / cloudflared)

While `python app.py` is running locally:

```bash
ngrok http 5000
# or
cloudflared tunnel --url http://localhost:5000
```

Share the printed HTTPS URL with classmates. Note that ngrok free URLs
are temporary — prefer Render/Railway for data collection that spans
more than one session.

---

## 8. Troubleshooting

* **"Database not found"** — run `python app.py` at least once, or run
  `python simulate.py --n 1 --reset` to create an empty database.
* **Plots not produced** — `matplotlib` is listed in `requirements.txt`;
  if you ran `pip install` without it the analysis still runs but skips
  the chart.
* **Everyone keeps seeing the same variant** — that is expected: the
  sticky cookie remembers your assignment. Clear site cookies (or open a
  private window) to be re-randomised.
