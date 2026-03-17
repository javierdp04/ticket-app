from flask import Blueprint, request, redirect, render_template, jsonify, current_app
from app.services import stripe_service, event_service, ticket_service

checkout_bp = Blueprint("checkout", __name__)


@checkout_bp.route("/checkout/create-session", methods=["POST"])
def create_session():
    event_id = request.form.get("event_id")
    buyer_name = request.form.get("buyer_name", "").strip()
    buyer_email = request.form.get("buyer_email", "").strip()
    quantity = int(request.form.get("quantity", 1))

    if not all([event_id, buyer_name, buyer_email, quantity > 0]):
        return "Datos incompletos", 400

    event = event_service.get_event(event_id)
    if not event or event["status"] != "active":
        return "Evento no disponible", 404

    available = event_service.get_available_tickets(event_id)
    if quantity > available:
        return "No hay suficientes entradas disponibles", 400

    session = stripe_service.create_checkout_session(event, buyer_name, buyer_email, quantity)
    return redirect(session.url, code=303)


@checkout_bp.route("/checkout/webhook", methods=["POST"])
def webhook():
    payload = request.get_data()
    sig_header = request.headers.get("Stripe-Signature")

    try:
        stripe_event = stripe_service.verify_webhook(payload, sig_header)
    except Exception:
        return "Firma invalida", 400

    if stripe_event["type"] == "checkout.session.completed":
        session = stripe_event["data"]["object"]
        metadata = session.get("metadata", {})
        event_id = metadata.get("event_id")
        quantity = int(metadata.get("quantity", 1))

        event = event_service.get_event(event_id)
        if event:
            ticket_service.create_tickets(session, event, quantity)

    return jsonify({"status": "ok"}), 200


@checkout_bp.route("/success")
def success():
    return render_template("success.html")


@checkout_bp.route("/cancel")
def cancel():
    return render_template("cancel.html")
