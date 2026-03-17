from flask import Blueprint, render_template, abort
from app.services import event_service
from app.utils.sanitize import valid_uuid

events_bp = Blueprint("events", __name__)


@events_bp.route("/event/<event_id>")
def event_detail(event_id):
    event_id = valid_uuid(event_id)
    if not event_id:
        abort(404)
    event = event_service.get_event(event_id)
    if not event or event["status"] == "finished":
        abort(404)
    available = event_service.get_available_tickets(event_id)
    return render_template("event_detail.html", event=event, available=available)
