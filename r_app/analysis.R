# =====================================================================
# A/B-test analysis (R)
# =====================================================================
#
# Reads the SQLite event log written by the R Shiny app (or the Python
# version -- the schema is identical) and produces, for every
# experiment:
#
#   * per-variant impression counts, conversion counts, conversion rates
#   * 95% Wilson confidence intervals
#   * two-proportion z-test (B vs A)
#   * Pearson chi-squared on the 2x2 contingency table
#   * absolute and relative lift
#   * bootstrap 95% CI for the relative lift
#   * bar-chart PNG of the two rates per experiment
#
# Usage
# -----
#     Rscript analysis.R                                  # default db + reports/
#     Rscript analysis.R --db some.db --out outdir/
# =====================================================================

suppressPackageStartupMessages({
  library(DBI)
  library(RSQLite)
})

# ---------------------------------------------------------------------

parse_args <- function(args) {
  out <- list(db = Sys.getenv("AB_DB_PATH", unset = "ab_test.db"),
              out = "reports")
  i <- 1
  while (i <= length(args)) {
    a <- args[[i]]
    if (a %in% c("--db", "-d"))    { out$db  <- args[[i + 1]]; i <- i + 2; next }
    if (a %in% c("--out", "-o"))   { out$out <- args[[i + 1]]; i <- i + 2; next }
    stop("Unknown argument: ", a)
  }
  out
}

load_events <- function(db_path) {
  if (!file.exists(db_path)) {
    stop("Database not found at '", db_path,
         "'. Run the Shiny app or simulate.R first.")
  }
  con <- dbConnect(SQLite(), db_path)
  on.exit(dbDisconnect(con), add = TRUE)
  dbGetQuery(con, "SELECT * FROM events")
}

aggregate_events <- function(df) {
  if (nrow(df) == 0) {
    return(data.frame(experiment = character(), variant = character(),
                      impressions = integer(), conversions = integer()))
  }
  agg <- aggregate(
    list(n = df$id),
    by = list(experiment = df$experiment,
              variant    = df$variant,
              event_type = df$event_type),
    FUN = length
  )
  wide <- reshape(agg, idvar = c("experiment", "variant"),
                  timevar = "event_type", direction = "wide")
  colnames(wide) <- gsub("^n\\.", "", colnames(wide))
  if (!"impression" %in% colnames(wide)) wide$impression <- 0
  if (!"conversion" %in% colnames(wide)) wide$conversion <- 0
  wide$impression[is.na(wide$impression)] <- 0
  wide$conversion[is.na(wide$conversion)] <- 0
  data.frame(
    experiment  = wide$experiment,
    variant     = wide$variant,
    impressions = as.integer(wide$impression),
    conversions = as.integer(wide$conversion),
    stringsAsFactors = FALSE
  )
}

wilson_ci <- function(x, n, conf = 0.95) {
  if (n == 0) return(c(0, 0))
  z <- qnorm(1 - (1 - conf) / 2)
  p <- x / n
  denom  <- 1 + z^2 / n
  centre <- (p + z^2 / (2 * n)) / denom
  half   <- z * sqrt((p * (1 - p) + z^2 / (4 * n)) / n) / denom
  c(max(0, centre - half), min(1, centre + half))
}

bootstrap_rel_lift <- function(xa, na, xb, nb, n_boot = 20000, seed = 42) {
  if (na == 0 || nb == 0 || xa == 0) {
    return(c(NA_real_, NA_real_))
  }
  set.seed(seed)
  pa <- xa / na
  pb <- xb / nb
  da <- rbinom(n_boot, na, pa) / na
  db <- rbinom(n_boot, nb, pb) / nb
  da[da == 0] <- NA
  lifts <- (db - da) / da
  unname(quantile(lifts, c(0.025, 0.975), na.rm = TRUE))
}

analyse_experiment <- function(name, rows, out_dir) {
  if (nrow(rows) == 0) {
    message("[", name, "] no data -- skipping.")
    return(invisible(NULL))
  }

  cat("\n=== Experiment: ", name, " ===\n", sep = "")
  for (i in seq_len(nrow(rows))) {
    v <- rows$variant[i]
    x <- rows$conversions[i]; n <- rows$impressions[i]
    rate <- if (n == 0) 0 else x / n
    ci <- wilson_ci(x, n)
    cat(sprintf("  Variant %s: %5d/%-5d = %6.2f%%   95%% CI [%.3f, %.3f]\n",
                v, x, n, rate * 100, ci[1], ci[2]))
  }

  if (all(c("A", "B") %in% rows$variant)) {
    a <- rows[rows$variant == "A", ]
    b <- rows[rows$variant == "B", ]
    xa <- a$conversions; na <- a$impressions
    xb <- b$conversions; nb <- b$impressions

    ztest <- suppressWarnings(prop.test(c(xb, xa), c(nb, na),
                                        correct = FALSE))
    pa <- if (na == 0) 0 else xa / na
    pb <- if (nb == 0) 0 else xb / nb
    p_pool <- (xa + xb) / (na + nb)
    se <- sqrt(p_pool * (1 - p_pool) * (1 / na + 1 / nb))
    z  <- if (se == 0) NA_real_ else (pb - pa) / se

    ct <- matrix(c(xa, na - xa, xb, nb - xb), nrow = 2, byrow = TRUE)
    chi <- suppressWarnings(chisq.test(ct, correct = FALSE))

    abs_lift <- pb - pa
    rel_lift <- if (pa == 0) NA_real_ else (pb - pa) / pa
    boot_ci <- bootstrap_rel_lift(xa, na, xb, nb)

    cat("\n  Two-proportion z-test (B vs A)\n")
    cat(sprintf("    z         = %+.3f\n", z))
    cat(sprintf("    p-value   = %.4f\n", ztest$p.value))

    cat("\n  Pearson chi-squared (1 dof)\n")
    cat(sprintf("    chi2      = %.3f\n", unname(chi$statistic)))
    cat(sprintf("    p-value   = %.4f\n", chi$p.value))

    cat("\n  Effect size\n")
    cat(sprintf("    Abs. lift = %+.4f (%+.2f pp)\n", abs_lift, abs_lift * 100))
    cat(sprintf("    Rel. lift = %+.2f%%\n", rel_lift * 100))
    cat(sprintf("    95%% bootstrap CI for rel. lift: [%+.2f%%, %+.2f%%]\n",
                boot_ci[1] * 100, boot_ci[2] * 100))

    verdict <- if (!is.na(ztest$p.value) && ztest$p.value < 0.05) {
      "Statistically significant at \u03B1 = 0.05"
    } else {
      "NOT statistically significant at \u03B1 = 0.05"
    }
    cat("\n  Verdict: ", verdict, "\n", sep = "")

    plot_variants(name, a, b, out_dir)
  } else {
    cat("  Only one variant has data -- skipping inferential tests.\n")
  }
}

plot_variants <- function(name, a, b, out_dir) {
  dir.create(out_dir, showWarnings = FALSE, recursive = TRUE)
  path <- file.path(out_dir, paste0(name, "_rates.png"))

  pa <- if (a$impressions == 0) 0 else a$conversions / a$impressions
  pb <- if (b$impressions == 0) 0 else b$conversions / b$impressions
  ci_a <- wilson_ci(a$conversions, a$impressions)
  ci_b <- wilson_ci(b$conversions, b$impressions)

  png(path, width = 720, height = 540, res = 150)
  on.exit(dev.off(), add = TRUE)
  rates <- c(pa, pb)
  labs  <- c(sprintf("A\n(n=%d)", a$impressions),
             sprintf("B\n(n=%d)", b$impressions))
  ymax  <- max(c(rates, ci_a[2], ci_b[2])) * 1.25
  if (ymax < 0.05) ymax <- 0.05

  bp <- barplot(rates, names.arg = labs, ylim = c(0, ymax),
                col = c("#94a3b8", "#5b6cff"),
                border = "#0f172a",
                main = paste0(name, " -- conversion rate by variant\n",
                              "(error bars = 95% Wilson CI)"),
                ylab = "Conversion rate")
  segments(bp, c(ci_a[1], ci_b[1]), bp, c(ci_a[2], ci_b[2]), lwd = 2)
  arrows(bp, c(ci_a[1], ci_b[1]), bp, c(ci_a[2], ci_b[2]),
         angle = 90, code = 3, length = 0.08, lwd = 2)
  text(bp, rates, sprintf("%.1f%%", rates * 100), pos = 3,
       offset = 0.6, font = 2)

  message("  Plot saved to ", path)
}

main <- function(args) {
  opts <- parse_args(args)
  df <- load_events(opts$db)
  agg <- aggregate_events(df)
  if (nrow(agg) == 0) { cat("No events in database yet.\n"); return(invisible(0)) }

  dir.create(opts$out, showWarnings = FALSE, recursive = TRUE)
  write.csv(agg, file.path(opts$out, "summary.csv"), row.names = FALSE)

  for (exp_name in sort(unique(agg$experiment))) {
    analyse_experiment(exp_name, agg[agg$experiment == exp_name, ], opts$out)
  }
  cat(sprintf("\nCSV summary written to %s\n",
              file.path(opts$out, "summary.csv")))
  invisible(0)
}

if (!interactive()) {
  main(commandArgs(trailingOnly = TRUE))
}
