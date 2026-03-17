import json
import stripe
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

    # Recoger nombres de asistentes
    if quantity > 1:
        attendee_names = []
        for i in range(1, quantity + 1):
            name = request.form.get(f"attendee_name_{i}", "").strip()
            if not name:
                return "Falta el nombre de algún asistente", 400
            attendee_names.append(name)
    else:
        attendee_names = [buyer_name]

    event = event_service.get_event(event_id)
    if not event or event["status"] != "active":
        return "Evento no disponible", 404

    available = event_service.get_available_tickets(event_id)
    if quantity > available:
        return "No hay suficientes entradas disponibles", 400

    session = stripe_service.create_checkout_session(
        event, buyer_name, buyer_email, quantity, attendee_names
    )
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
    session_id = request.args.get("session_id")
    if session_id:
        try:
            stripe.api_key = current_app.config["STRIPE_SECRET_KEY"]
            session = stripe.checkout.Session.retrieve(session_id)

            if session.payment_status == "paid":
                metadata = session.get("metadata", {})
                event_id = metadata.get("event_id")
                quantity = int(metadata.get("quantity", 1))

                event = event_service.get_event(event_id)
                if event:
                    from app.models import ticket as ticket_model
                    existing = ticket_model.get_ticket_by_session(session_id)
                    if not existing:
                        ticket_service.create_tickets(session, event, quantity)
        except Exception as e:
            current_app.logger.error(f"Error procesando pago en success: {e}")

    return render_template("success.html")


@checkout_bp.route("/cancel")
def cancel():
    return render_template("cancel.html")
