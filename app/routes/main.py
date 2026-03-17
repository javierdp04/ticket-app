from flask import Blueprint, render_template
from app.services import event_service

main_bp = Blueprint("main", __name__)


@main_bp.route("/")
def index():
    events = event_service.get_active_events()
    return render_template("index.html", events=events)
