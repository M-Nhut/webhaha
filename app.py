"""Flask composition root; HTTP handlers live in routes and startup in services."""
import os
import sys

from flask import Flask, send_from_directory
from whitenoise import WhiteNoise

from config import PROJECT_ROOT, configure_application
from extensions import init_extensions
from routes import register_all_routes
# Keep the backfill helper importable from ``app`` for existing maintenance
# scripts; all startup orchestration stays behind ``initialize_database``.
from services.database_startup import backfill_adaptive_learning_history, initialize_database

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

basedir = str(PROJECT_ROOT)
app = Flask(__name__)
# Direct local runs edit static files while the development server stays up.
# Recheck each file so response headers match its current contents.
app.wsgi_app = WhiteNoise(
    app.wsgi_app,
    root=os.path.join(basedir, "static"),
    prefix="static/",
    autorefresh=__name__ == "__main__",
    max_age=0 if __name__ == "__main__" else 60,
)


@app.route("/favicon.ico")
def favicon():
    return send_from_directory(
        os.path.join(basedir, "static", "images"),
        "logo-transparent.png",
        mimetype="image/png",
    )


IS_VERCEL = configure_application(app)
init_extensions(app)
register_all_routes(app, PROJECT_ROOT, IS_VERCEL)

# Retain the existing startup order for both local and Vercel entry points.
with app.app_context():
    initialize_database()

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5003)
