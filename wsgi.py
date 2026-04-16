"""
WSGI entry point used by production servers (gunicorn, uWSGI, etc).

Ensures the SQLite schema exists before the first request, then
exposes the Flask ``app`` object under the conventional name.
"""

from app import app, init_db

init_db()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
