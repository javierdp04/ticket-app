import os

import click
from flask import Flask
from flask_mail import Mail
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from pymongo import MongoClient
from werkzeug.middleware.proxy_fix import ProxyFix

mail = Mail()
_rate_limit_storage = os.getenv("REDIS_URL", "memory://")
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["120 per minute"],
    storage_uri=_rate_limit_storage,
)
mongo_client = None
db = None


def create_app():
    global mongo_client, db

    app = Flask(__name__)
    app.config.from_object("app.config.Config")

    # Confiar en cabeceras de proxy (Nginx)
    # x_for=1: un nivel de proxy para X-Forwarded-For
    # x_proto=1: X-Forwarded-Proto para detectar HTTPS
    if not app.debug:
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    # MongoDB
    mongo_client = MongoClient(app.config["MONGO_URI"])
    db = mongo_client.get_default_database()

    # Flask-Mail
    mail.init_app(app)

    # Rate limiter
    limiter.init_app(app)

    # Registrar blueprints
    from app.routes.main import main_bp
    from app.routes.events import events_bp
    from app.routes.checkout import checkout_bp
    from app.routes.tickets import tickets_bp
    from app.routes.scanner import scanner_bp
    from app.routes.admin import admin_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(events_bp)
    app.register_blueprint(checkout_bp)
    app.register_blueprint(tickets_bp)
    app.register_blueprint(scanner_bp)
    app.register_blueprint(admin_bp)

    from app.utils.csrf import generate_csrf_token
    app.jinja_env.globals["csrf_token"] = generate_csrf_token

    @app.after_request
    def set_security_headers(response):
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        if not app.debug:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response

    @app.cli.command("cleanup-reservations")
    @click.option("--max-age", default=35, help="Max reservation age in minutes")
    def cleanup_reservations_cmd(max_age):
        """Libera reservas huerfanas mas antiguas que --max-age minutos."""
        from app.services import event_service
        count = event_service.cleanup_stale_reservations(max_age)
        click.echo(f"Reservas liberadas: {count}")

    return app
