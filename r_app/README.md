# R Shiny Version — A/B Test Website

This directory contains the **R Shiny** implementation of the project.
It is functionally identical to the Python (`app.py`) version at the
repository root — same two experiments, same SQLite event schema, same
statistical tests — but written entirely in R so it can be run and
deployed to **shinyapps.io** without touching Python.

```
r_app/
├── app.R         # The Shiny app (UI + server)
├── analysis.R    # Statistical analysis (Wilson CI, z-test, chi2, bootstrap)
├── simulate.R    # Synthetic-event generator
└── deploy.R      # One-shot shinyapps.io deploy script
```

## 1. Prerequisites

Install R 4.x from <https://cran.r-project.org/> (or <https://posit.co/download/rstudio-desktop/> if you want the IDE).

Then install the R packages:

```r
install.packages(c("shiny", "DBI", "RSQLite", "rsconnect"))
```

## 2. Run locally

From a terminal:

```bash
cd r_app
Rscript -e 'shiny::runApp(".", port = 8000, host = "127.0.0.1")'
```

…or from RStudio: open `r_app/app.R` and click **Run App**.

Visit <http://127.0.0.1:8000>.  Click between the **Newsletter**, **Register**,
and **Live stats** tabs and submit a few forms — the stats tab refreshes every
five seconds.

## 3. Force a variant via URL

```
http://.../?discount=A
http://.../?discount=B
http://.../?form=A
http://.../?form=B
http://.../?group=A          # legacy — sets both experiments
```

Useful for targeted share links. **Do not** use these URLs when
collecting primary-analysis data because they break randomisation.

## 4. Simulate data (optional, for demoing the analysis pipeline)

```bash
Rscript simulate.R --n 2000 --reset
```

## 5. Run the statistical analysis

```bash
Rscript analysis.R
```

Per-experiment output includes: per-variant Wilson 95 % CI,
two-proportion z-test, Pearson chi-squared, absolute & relative lift,
and a 20 000-sample bootstrap 95 % CI for the relative lift. PNG plots
and a `summary.csv` are written to `reports/`.

## 6. Deploy to shinyapps.io

One-time setup on your laptop:

1. Create a free account at <https://www.shinyapps.io/>.
2. Open <https://www.shinyapps.io/admin/#/tokens> → **Add Token → Show**.
   You will see a block like:
   ```r
   rsconnect::setAccountInfo(
     name   = "yourname",
     token  = "…",
     secret = "…"
   )
   ```
   Paste and run it inside R once.

Then to publish (and for every future update):

```bash
cd r_app
Rscript deploy.R
```

…or from R/RStudio:

```r
rsconnect::deployApp("r_app", appName = "ab-test-experiment")
```

After ~2 minutes the console prints your public URL, e.g.

```
https://yourname.shinyapps.io/ab-test-experiment/
```

Share that link with classmates to collect data.

> **Note on SQLite persistence.** shinyapps.io will occasionally restart
> idle containers, which resets `ab_test.db`. For a short-running class
> experiment this is usually fine (most traffic arrives while the app is
> warm). If you need persistence across restarts, either run the app on
> a service with a mounted volume or use an external database.
