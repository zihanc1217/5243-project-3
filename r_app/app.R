# =====================================================================
# A/B Test R Shiny App
# =====================================================================
#
# Implements the two experiments described in the project brief:
#
# Experiment 1 -- Discount / Offer Page (Newsletter tab)
#     Variant A: "Join Our Newsletter"           (no discount)
#     Variant B: "Join & Get 10% Off"            (discount incentive)
#     Metric:    newsletter conversion rate
#
# Experiment 2 -- Form Length Test        (Register tab)
#     Variant A: email only
#     Variant B: name + email + school
#     Metric:    registration submission rate
#
# Randomisation
# -------------
# Each Shiny session gets an unbiased 50/50 assignment for each
# experiment, unless the user overrides it with a URL query string:
#   ?discount=A|B   ?form=A|B   ?group=A|B (legacy -- sets both)
#
# Data
# ----
# Every impression and conversion is appended to a SQLite database
# (`ab_test.db` by default, or $AB_DB_PATH if set).  This is the same
# schema used by the Python version and by `analysis.R` / `simulate.R`.
#
# Running locally
# ---------------
#     Rscript -e 'shiny::runApp("r_app", port = 5080, host = "0.0.0.0")'
#
# Deploying to shinyapps.io
# -------------------------
#     Rscript r_app/deploy.R          # reads tokens from env vars
# =====================================================================

library(shiny)
library(DBI)
library(RSQLite)

# ---------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------

DB_PATH <- Sys.getenv("AB_DB_PATH", unset = "ab_test.db")

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

init_db <- function(path = DB_PATH) {
  dir.create(dirname(path), showWarnings = FALSE, recursive = TRUE)
  con <- dbConnect(SQLite(), path)
  on.exit(dbDisconnect(con), add = TRUE)
  for (stmt in strsplit(SCHEMA, ";")[[1]]) {
    stmt <- trimws(stmt)
    if (nzchar(stmt)) dbExecute(con, stmt)
  }
  invisible(TRUE)
}

log_event <- function(user_id, experiment, variant, event_type,
                      user_agent = "", referrer = "", payload = NA_character_) {
  con <- dbConnect(SQLite(), DB_PATH)
  on.exit(dbDisconnect(con), add = TRUE)
  dbExecute(
    con,
    "INSERT INTO events
         (user_id, experiment, variant, event_type,
          created_at, user_agent, referrer, payload)
     VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
    params = list(
      user_id,
      experiment,
      variant,
      event_type,
      format(Sys.time(), "%Y-%m-%dT%H:%M:%S", tz = "UTC"),
      user_agent,
      referrer,
      payload
    )
  )
}

# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------

parse_query <- function(search) {
  if (is.null(search) || !nzchar(search)) return(list())
  shiny::parseQueryString(search)
}

resolve_variant <- function(q, key) {
  for (k in c(key, "group")) {
    val <- q[[k]]
    if (!is.null(val)) {
      up <- toupper(trimws(val))
      if (up %in% c("A", "B")) return(up)
    }
  }
  sample(c("A", "B"), 1)
}

new_user_id <- function() {
  paste0(
    format(as.integer(Sys.time()), scientific = FALSE),
    "-",
    paste(sample(c(letters, 0:9), 16, replace = TRUE), collapse = "")
  )
}

# ---------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------

app_css <- "
:root {
  --primary:#5b6cff; --accent:#ff7a59;
  --ink:#0f172a; --ink-soft:#475569;
  --border:#e2e8f0; --surface:#ffffff;
}
body { background: linear-gradient(180deg,#f9fafc 0%,#eef2ff 100%); }
.navbar { background:#fff !important; border-bottom:1px solid var(--border); }
.navbar-brand { font-weight:800; letter-spacing:-0.02em; }

.hero-card {
  max-width: 680px; margin: 2.5rem auto; padding: 2.5rem;
  background:#fff; border-radius:14px; border:1px solid var(--border);
  box-shadow: 0 20px 60px rgba(15,23,42,.08); text-align:center;
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
  border-radius:8px; transform: rotate(-3deg); font-size:.85rem;
}
.hero-sub { color: var(--ink-soft); font-size:1.05rem; line-height:1.55; }
.cta-btn { width:100%; padding:.9rem 1.2rem !important; border:none !important;
           background: var(--primary) !important; color:#fff !important;
           border-radius:999px !important; font-weight:700 !important;
           font-size:1rem !important; cursor:pointer;
           transition: transform .12s, box-shadow .12s; }
.cta-btn:hover { transform: translateY(-1px);
                 box-shadow: 0 10px 24px rgba(91,108,255,.35); }
.cta-btn.offer { background: var(--accent) !important; color:#1a0d07 !important; }
.form-group input.form-control {
  padding:.85rem 1rem !important; border-radius:10px !important;
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
               border-radius:6px; background:#eef2ff;
               color: var(--primary);
               font-size:.75rem; font-weight:700; letter-spacing:.1em; }
.msg-ok    { color:#059669; font-weight:600; }
.msg-error { color:#b91c1c; font-weight:600; }
"

ui <- navbarPage(
  title = "Lumen Labs",
  id = "nav",
  header = tagList(
    tags$head(
      tags$meta(charset = "utf-8"),
      tags$meta(name = "viewport",
                content = "width=device-width, initial-scale=1"),
      tags$style(HTML(app_css))
    )
  ),
  tabPanel("Newsletter", div(class = "container", uiOutput("newsletter_ui"))),
  tabPanel("Register",   div(class = "container", uiOutput("register_ui"))),
  tabPanel("Live stats",
           div(class = "container",
               style = "max-width:860px; margin:2rem auto;",
               h2("Live experiment stats"),
               p(class = "fine-print",
                 "Real-time impressions and conversions per experiment / ",
                 "variant.  Run ", tags$code("Rscript analysis.R"),
                 " for full statistical inference."),
               uiOutput("stats_ui"))),
  footer = tags$footer(
    style = "text-align:center; padding:1.5rem;",
    tags$p(class = "fine-print",
           "A/B-testing class project \u00B7 Share ",
           tags$code("?discount=A"), " / ",
           tags$code("?discount=B"), " / ",
           tags$code("?form=A"), " / ",
           tags$code("?form=B"),
           " to force a variant.")
  )
)

# ---------------------------------------------------------------------
# Server
# ---------------------------------------------------------------------

server <- function(input, output, session) {
  init_db()

  # Session-level state ---------------------------------------------
  q_initial <- parse_query(session$clientData$url_search)
  uid <- new_user_id()

  variant_discount <- reactiveVal(resolve_variant(q_initial, "discount"))
  variant_form     <- reactiveVal(resolve_variant(q_initial, "form"))

  impressed <- reactiveValues(discount = FALSE, form_length = FALSE)
  msg_newsletter <- reactiveVal("")
  msg_register   <- reactiveVal("")
  stats_tick     <- reactiveVal(0L)

  user_agent <- isolate({
    ua <- session$request$HTTP_USER_AGENT
    if (is.null(ua)) "" else ua
  })
  referrer <- isolate({
    r <- session$request$HTTP_REFERER
    if (is.null(r)) "" else r
  })

  # Record an impression exactly once per tab per session
  observe({
    tab <- input$nav
    req(tab)
    if (tab == "Newsletter" && !impressed$discount) {
      impressed$discount <- TRUE
      log_event(uid, "discount", variant_discount(), "impression",
                user_agent = user_agent, referrer = referrer)
    } else if (tab == "Register" && !impressed$form_length) {
      impressed$form_length <- TRUE
      log_event(uid, "form_length", variant_form(), "impression",
                user_agent = user_agent, referrer = referrer)
    }
  })

  # ---------------------------------------------------- Newsletter UI

  output$newsletter_ui <- renderUI({
    v <- variant_discount()
    is_b <- v == "B"
    headline <- if (is_b) "Join & Get 10% Off" else "Join Our Newsletter"
    subhead <- if (is_b) {
      paste("Subscribe today and we'll email you a coupon for 10% off your",
            "first order \u2014 plus weekly tips, new arrivals, and",
            "subscriber-only deals.")
    } else {
      paste("Subscribe today for weekly tips, new arrivals, and",
            "insider updates delivered straight to your inbox.")
    }
    badge_text <- if (is_b) "Limited time offer" else "Newsletter"
    cta_label  <- if (is_b) "Claim 10% Off" else "Subscribe"

    feedback <- msg_newsletter()
    feedback_el <- if (!nzchar(feedback)) NULL else {
      cls <- if (startsWith(feedback, "\u2713")) "msg-ok" else "msg-error"
      tags$p(feedback, class = cls)
    }

    div(class = "hero-card",
      tags$span(badge_text,
                class = paste("badge-pill", if (is_b) "offer" else "")),
      h1(class = "hero-title",
         headline,
         if (is_b) tags$span("10% OFF", class = "ribbon")),
      p(class = "hero-sub", subhead),
      textInput("newsletter_email", NULL,
                placeholder = "you@example.com", width = "100%"),
      actionButton("subscribe_btn", cta_label,
                   class = paste("cta-btn", if (is_b) "offer" else "")),
      feedback_el,
      tags$p(class = "fine-print",
             "Your variant: ",
             tags$span(v, class = "variant-tag"))
    )
  })

  # ---------------------------------------------------- Register UI

  output$register_ui <- renderUI({
    v <- variant_form()
    is_b <- v == "B"

    feedback <- msg_register()
    feedback_el <- if (!nzchar(feedback)) NULL else {
      cls <- if (startsWith(feedback, "\u2713")) "msg-ok" else "msg-error"
      tags$p(feedback, class = cls)
    }

    extras_top <- if (is_b) {
      textInput("register_name", "Full name",
                placeholder = "Ada Lovelace", width = "100%")
    } else NULL
    extras_bottom <- if (is_b) {
      textInput("register_school", "School",
                placeholder = "Columbia University", width = "100%")
    } else NULL

    div(class = "hero-card",
      h1("Create your free account", class = "hero-title"),
      p(class = "hero-sub",
        paste("Join thousands of students using Lumen Labs to track study",
              "progress and connect with classmates.")),
      extras_top,
      textInput("register_email", "Email address",
                placeholder = "you@example.com", width = "100%"),
      extras_bottom,
      actionButton("register_btn", "Create my account", class = "cta-btn"),
      feedback_el,
      tags$p(class = "fine-print",
             "Your variant: ",
             tags$span(v, class = "variant-tag"))
    )
  })

  # ---------------------------------------------------- Stats UI

  observe({
    invalidateLater(5000, session)
    stats_tick(stats_tick() + 1L)
  })

  output$stats_ui <- renderUI({
    stats_tick()  # reactive dependency
    con <- dbConnect(SQLite(), DB_PATH)
    on.exit(dbDisconnect(con), add = TRUE)
    rows <- tryCatch(
      dbGetQuery(con, "
        SELECT experiment,
               variant,
               SUM(event_type = 'impression') AS impressions,
               SUM(event_type = 'conversion') AS conversions
          FROM events
         GROUP BY experiment, variant
         ORDER BY experiment, variant
      "),
      error = function(e) data.frame()
    )

    if (nrow(rows) == 0) {
      return(tags$p(class = "fine-print",
                    paste("No events yet \u2014 interact with the Newsletter",
                          "/ Register tabs to generate data.")))
    }
    rows$rate <- ifelse(rows$impressions > 0,
                        rows$conversions / rows$impressions, 0)

    by_exp <- split(rows, rows$experiment)
    cards <- lapply(names(by_exp), function(exp_name) {
      g <- by_exp[[exp_name]]
      body <- lapply(seq_len(nrow(g)), function(i) {
        tags$tr(
          tags$td(tags$strong(g$variant[i])),
          tags$td(as.character(g$impressions[i])),
          tags$td(as.character(g$conversions[i])),
          tags$td(sprintf("%.2f%%", 100 * g$rate[i]))
        )
      })
      div(class = "stats-card",
          h3(tools::toTitleCase(gsub("_", " ", exp_name))),
          tags$table(
            tags$thead(tags$tr(
              tags$th("Variant"), tags$th("Impressions"),
              tags$th("Conversions"), tags$th("Rate")
            )),
            do.call(tags$tbody, body)
          ))
    })
    do.call(tagList, cards)
  })

  # ---------------------------------------------------- Handlers

  observeEvent(input$subscribe_btn, {
    email <- trimws(input$newsletter_email %||% "")
    if (!nzchar(email) || !grepl("@", email, fixed = TRUE)) {
      msg_newsletter("Please enter a valid email address.")
      return()
    }
    v <- variant_discount()
    log_event(uid, "discount", v, "conversion",
              user_agent = user_agent, referrer = referrer,
              payload = paste0("email=", email))
    if (v == "B") {
      msg_newsletter(sprintf(
        "\u2713 Subscribed! Your 10%% off coupon is on its way to %s.", email))
    } else {
      msg_newsletter("\u2713 Subscribed! Thanks \u2014 welcome to Lumen Labs.")
    }
    stats_tick(stats_tick() + 1L)
  })

  observeEvent(input$register_btn, {
    email <- trimws(input$register_email %||% "")
    if (!nzchar(email) || !grepl("@", email, fixed = TRUE)) {
      msg_register("Please enter a valid email address.")
      return()
    }
    v <- variant_form()
    payload <- paste0("email=", email)
    if (v == "B") {
      name   <- trimws(input$register_name %||% "")
      school <- trimws(input$register_school %||% "")
      if (!nzchar(name) || !nzchar(school)) {
        msg_register("Please fill in every required field.")
        return()
      }
      payload <- sprintf("email=%s; name=%s; school=%s", email, name, school)
    }
    log_event(uid, "form_length", v, "conversion",
              user_agent = user_agent, referrer = referrer,
              payload = payload)
    msg_register("\u2713 Account created \u2014 welcome to Lumen Labs!")
    stats_tick(stats_tick() + 1L)
  })
}

# `%||%` is only in Shiny >= 1.6; redefine locally for safety.
`%||%` <- function(a, b) if (is.null(a)) b else a

shinyApp(ui, server)
