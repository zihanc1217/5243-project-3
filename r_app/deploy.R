# =====================================================================
# Deploy this R Shiny app to shinyapps.io.
#
# Prerequisites (one-time on your laptop):
#
#   install.packages("rsconnect")
#
#   # Grab ACCOUNT / TOKEN / SECRET from
#   #   https://www.shinyapps.io/admin/#/tokens
#   rsconnect::setAccountInfo(
#     name   = "YOUR-ACCOUNT",
#     token  = "YOUR-TOKEN",
#     secret = "YOUR-SECRET"
#   )
#
# After that, running this script publishes the app (or updates an
# existing deployment):
#
#   Rscript r_app/deploy.R
#
# Environment variables you can override:
#   APP_NAME   - shinyapps.io app slug  (default: ab-test-experiment)
#   APP_TITLE  - human-readable title   (default: "A/B Test Experiment")
# =====================================================================

library(rsconnect)

`%||%` <- function(a, b) if (is.null(a) || !nzchar(a)) b else a

# Resolve the directory that contains this script so the deploy works
# regardless of the caller's working directory.
resolve_script_dir <- function() {
  # When run with `Rscript`, the --file=... argument points at this file.
  args <- commandArgs(trailingOnly = FALSE)
  file_arg <- sub("^--file=", "", args[grepl("^--file=", args)])
  if (length(file_arg) == 1 && nzchar(file_arg)) {
    return(normalizePath(dirname(file_arg), mustWork = TRUE))
  }
  # Fallback to the current working directory.
  normalizePath(getwd(), mustWork = TRUE)
}

app_dir <- resolve_script_dir()
app_name  <- Sys.getenv("APP_NAME")  %||% "ab-test-experiment"
app_title <- Sys.getenv("APP_TITLE") %||% "A/B Test Experiment"

accounts <- tryCatch(rsconnect::accounts(), error = function(e) NULL)
if (is.null(accounts) || nrow(accounts) == 0) {
  stop(
    "No rsconnect account configured. Run:\n",
    "  rsconnect::setAccountInfo(name = '...', token = '...', secret = '...')\n",
    "using the values from https://www.shinyapps.io/admin/#/tokens"
  )
}

cat(sprintf("Deploying '%s' (title: %s) to shinyapps.io account '%s'...\n",
            app_name, app_title, accounts$name[1]))

rsconnect::deployApp(
  appDir      = app_dir,
  appName     = app_name,
  appTitle    = app_title,
  appFiles    = c("app.R", "analysis.R", "simulate.R"),
  server      = "shinyapps.io",
  forceUpdate = TRUE,
  launch.browser = FALSE
)
