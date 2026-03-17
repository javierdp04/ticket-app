from flask import Blueprint, render_template, request, jsonify, session, abort

from app import limiter
from app.services import event_service, ticket_service
from app.utils.sanitize import valid_uuid, valid_pin

scanner_bp = Blueprint("scanner", __name__)


@scanner_bp.route("/scanner/<event_id>")
def scanner(event_id):
    event_id = valid_uuid(event_id)
    if not event_id:
        abort(404)
    event = event_service.get_event(event_id)
    if not event:
        abort(404)

    authenticated = session.get(f"scanner_auth_{event_id}", False)
    return render_template("scanner.html", event=event, authenticated=authenticated)


@scanner_bp.route("/scanner/auth", methods=["POST"])
@limiter.limit("10 per minute")
def scanner_auth():
    data = request.get_json(force=True, silent=True)
    if not data:
        return jsonify({"success": False, "message": "Datos no recibidos"}), 400

    event_id = valid_uuid(data.get("event_id"))
    pin = valid_pin(data.get("pin", ""))

    if not event_id or not pin:
        return jsonify({"success": False, "message": "Faltan datos"}), 400

    if event_service.verify_scanner_pin(event_id, pin):
        session[f"scanner_auth_{event_id}"] = True
        return jsonify({"success": True})

    return jsonify({"success": False, "message": "PIN incorrecto"}), 401


@scanner_bp.route("/scanner/validate", methods=["POST"])
@limiter.limit("30 per minute")
def validate():
    data = request.get_json(force=True, silent=True)
    if not data:
        return jsonify({"valid": False, "reason": "Datos no recibidos"}), 400

    ticket_id = valid_uuid(data.get("ticket_id"))
    event_id = valid_uuid(data.get("event_id"))

    if not ticket_id or not event_id:
        return jsonify({"valid": False, "reason": "Datos invalidos"}), 400

    if not session.get(f"scanner_auth_{event_id}", False):
        return jsonify({"valid": False, "reason": "No autenticado"}), 401

    ticket = ticket_service.get_ticket(ticket_id)
    if ticket and ticket["event_id"] != event_id:
        return jsonify({"valid": False, "reason": "Entrada de otro evento"}), 400

    result = ticket_service.validate_ticket(ticket_id)
    return jsonify(result)
