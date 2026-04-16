"""
WSGI entry point for the legacy Flask implementation (``flask_app.py``).

The canonical app is the Shiny for Python app in ``app.py`` — use that
for deployment to shinyapps.io / Posit Connect.  This module exists so
the project can still be served with ``gunicorn`` on buildpack-style
hosts (Render, Heroku, Fly).
"""

from flask_app import app, init_db

init_db()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
