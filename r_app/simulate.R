# =====================================================================
# Simulate synthetic A/B-test events directly into the SQLite event log.
#
# Useful for developing / demoing the analysis pipeline before enough
# real users have interacted with the deployed Shiny app.
#
# Usage
# -----
#   Rscript simulate.R --n 2000 --reset
#   Rscript simulate.R --n 5000 --seed 7
# =====================================================================

suppressPackageStartupMessages({
  library(DBI)
  library(RSQLite)
})

SCHEMA <- "
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
"

parse_args <- function(args) {
  out <- list(
    db = Sys.getenv("AB_DB_PATH", unset = "ab_test.db"),
    n = 2000L, seed = 42L, reset = FALSE,
    discount_a = 0.10, discount_b = 0.15,
    form_a = 0.50, form_b = 0.35
  )
  i <- 1
  while (i <= length(args)) {
    a <- args[[i]]
    if (a == "--db")         { out$db    <- args[[i + 1]];                i <- i + 2; next }
    if (a %in% c("--n"))     { out$n     <- as.integer(args[[i + 1]]);    i <- i + 2; next }
    if (a %in% c("--seed"))  { out$seed  <- as.integer(args[[i + 1]]);    i <- i + 2; next }
    if (a == "--reset")      { out$reset <- TRUE;                          i <- i + 1; next }
    if (a == "--discount-a") { out$discount_a <- as.numeric(args[[i + 1]]); i <- i + 2; next }
    if (a == "--discount-b") { out$discount_b <- as.numeric(args[[i + 1]]); i <- i + 2; next }
    if (a == "--form-a")     { out$form_a     <- as.numeric(args[[i + 1]]); i <- i + 2; next }
    if (a == "--form-b")     { out$form_b     <- as.numeric(args[[i + 1]]); i <- i + 2; next }
    stop("Unknown argument: ", a)
  }
  out
}

ensure_schema <- function(con) {
  for (stmt in strsplit(SCHEMA, ";")[[1]]) {
    stmt <- trimws(stmt)
    if (nzchar(stmt)) dbExecute(con, stmt)
  }
}

random_uid <- function(n) {
  replicate(n, paste(sample(c(letters, 0:9), 24, replace = TRUE), collapse = ""))
}

simulate <- function(opts) {
  set.seed(opts$seed)
  dir.create(dirname(opts$db), showWarnings = FALSE, recursive = TRUE)
  con <- dbConnect(SQLite(), opts$db)
  on.exit(dbDisconnect(con), add = TRUE)
  ensure_schema(con)
  if (opts$reset) dbExecute(con, "DELETE FROM events")

  uids <- random_uid(opts$n)
  experiments <- sample(c("discount", "form_length"), opts$n, replace = TRUE)
  variants    <- sample(c("A", "B"), opts$n, replace = TRUE)

  p <- ifelse(experiments == "discount",
              ifelse(variants == "A", opts$discount_a, opts$discount_b),
              ifelse(variants == "A", opts$form_a,     opts$form_b))

  now <- Sys.time()
  rows <- list()
  for (i in seq_len(opts$n)) {
    ts_imp <- format(now - (opts$n - i), "%Y-%m-%dT%H:%M:%S", tz = "UTC")
    rows[[length(rows) + 1L]] <- list(
      uids[i], experiments[i], variants[i], "impression",
      ts_imp, "Simulator/1.0", "", NA_character_
    )
    if (runif(1) < p[i]) {
      ts_c <- format(now - (opts$n - i) + runif(1, 5, 120),
                     "%Y-%m-%dT%H:%M:%S", tz = "UTC")
      rows[[length(rows) + 1L]] <- list(
        uids[i], experiments[i], variants[i], "conversion",
        ts_c, "Simulator/1.0", "", "simulated=1"
      )
    }
  }
  # Build a data.frame from the rows in a single shot, then append it.
  df <- do.call(
    rbind.data.frame,
    lapply(rows, function(r) data.frame(
      user_id     = r[[1]],
      experiment  = r[[2]],
      variant     = r[[3]],
      event_type  = r[[4]],
      created_at  = r[[5]],
      user_agent  = r[[6]],
      referrer    = r[[7]],
      payload     = r[[8]],
      stringsAsFactors = FALSE
    ))
  )
  dbAppendTable(con, "events", df)

  total <- dbGetQuery(con, "SELECT COUNT(*) AS n FROM events")$n
  cat(sprintf(
    "Simulated %d users -> wrote %d events to %s (total events now: %d).\n",
    opts$n, nrow(df), opts$db, total))
}

if (!interactive()) {
  simulate(parse_args(commandArgs(trailingOnly = TRUE)))
}
