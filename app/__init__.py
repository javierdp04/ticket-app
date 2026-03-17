from flask import Flask
from flask_mail import Mail
from pymongo import MongoClient

mail = Mail()
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

    return app
