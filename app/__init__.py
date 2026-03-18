import click
from flask import Flask
from flask_mail import Mail
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from pymongo import MongoClient

mail = Mail()
limiter = Limiter(key_func=get_remote_address, default_limits=["120 per minute"], storage_uri="memory://")
mongo_client = None
db = None


def create_app():
    global mongo_client, db

    app = Flask(__name__)
    app.config.from_object("app.config.Config")

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

    @app.cli.command("cleanup-reservations")
    @click.option("--max-age", default=35, help="Max reservation age in minutes")
    def cleanup_reservations_cmd(max_age):
        """Libera reservas huerfanas mas antiguas que --max-age minutos."""
        from app.services import event_service
        count = event_service.cleanup_stale_reservations(max_age)
        click.echo(f"Reservas liberadas: {count}")

    return app
