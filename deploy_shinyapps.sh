#!/usr/bin/env bash
# Deploy the Shiny-for-Python app to shinyapps.io.
#
# Prerequisites (one-time):
#   pip install rsconnect-python
#   # Grab the token/secret from https://www.shinyapps.io/admin/#/tokens
#   rsconnect add \
#     --account <ACCOUNT> \
#     --name <NAME> \
#     --token <TOKEN> \
#     --secret <SECRET>
#
# After that, running ./deploy_shinyapps.sh will (re)publish the app.
set -euo pipefail

NAME="${SHINYAPPS_SERVER:-shinyapps}"
TITLE="${APP_TITLE:-A/B Test Experiment — Lumen Labs}"

cd "$(dirname "$0")"

echo "Deploying to shinyapps.io (server alias: $NAME, title: $TITLE)…"
rsconnect deploy shiny . \
    --name "$NAME" \
    --title "$TITLE" \
    --entrypoint app
