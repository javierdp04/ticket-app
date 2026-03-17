from flask import Blueprint, render_template, request, jsonify, session, abort
from app.services import event_service, ticket_service

scanner_bp = Blueprint("scanner", __name__)


@scanner_bp.route("/scanner/<event_id>")
def scanner(event_id):
    event = event_service.get_event(event_id)
    if not event:
        abort(404)

    authenticated = session.get(f"scanner_auth_{event_id}", False)
    return render_template("scanner.html", event=event, authenticated=authenticated)


@scanner_bp.route("/scanner/auth", methods=["POST"])
def scanner_auth():
    data = request.get_json()
    event_id = data.get("event_id")
    pin = data.get("pin", "").strip()

    if event_service.verify_scanner_pin(event_id, pin):
        session[f"scanner_auth_{event_id}"] = True
        return jsonify({"success": True})

    return jsonify({"success": False, "message": "PIN incorrecto"}), 401


@scanner_bp.route("/scanner/validate", methods=["POST"])
def validate():
    data = request.get_json()
    ticket_id = data.get("ticket_id")
    event_id = data.get("event_id")

    if not session.get(f"scanner_auth_{event_id}", False):
        return jsonify({"valid": False, "reason": "No autenticado"}), 401

    ticket = ticket_service.get_ticket(ticket_id)
    if ticket and ticket["event_id"] != event_id:
        return jsonify({"valid": False, "reason": "Entrada de otro evento"}), 400

    result = ticket_service.validate_ticket(ticket_id)
    return jsonify(result)
