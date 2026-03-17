import stripe
from flask import Blueprint, request, redirect, render_template, jsonify, current_app
from app import limiter
from app.services import stripe_service, event_service, ticket_service
from app.utils.sanitize import clean, valid_uuid, valid_email, valid_int

checkout_bp = Blueprint("checkout", __name__)


@checkout_bp.route("/checkout/create-session", methods=["POST"])
@limiter.limit("10 per minute")
def create_session():
    event_id = valid_uuid(request.form.get("event_id"))
    buyer_first_name = clean(request.form.get("buyer_first_name", ""), max_length=100)
    buyer_last_name = clean(request.form.get("buyer_last_name", ""), max_length=100)
    buyer_name = f"{buyer_first_name} {buyer_last_name}"
    buyer_email = valid_email(request.form.get("buyer_email", ""))

    if not all([event_id, buyer_first_name, buyer_last_name, buyer_email]):
        return "Datos incompletos", 400

    event = event_service.get_event(event_id)
    if not event or event["status"] != "active":
        return "Evento no disponible", 404

    # Recoger cantidades por tipo de entrada
    items = []
    for tt in event.get("ticket_types", []):
        qty = valid_int(request.form.get(f"quantity_{tt['type_id']}", 0), min_val=0, max_val=20, default=0)
        if qty > 0:
            items.append({
                "type_id": tt["type_id"],
                "type_name": tt["name"],
                "price": tt["price"],
                "quantity": qty,
            })

    total_quantity = sum(i["quantity"] for i in items)
    if total_quantity < 1:
        return "Selecciona al menos una entrada", 400

    # Recoger nombres de asistentes
    attendee_names = []
    for i in range(1, total_quantity + 1):
        first = clean(request.form.get(f"attendee_first_name_{i}", ""), max_length=100)
        last = clean(request.form.get(f"attendee_last_name_{i}", ""), max_length=100)
        if not first or not last:
            return "Falta el nombre de algún asistente", 400
        attendee_names.append(f"{first} {last}")

    # Reserva atomica por cada tipo
    reserved = []
    for item in items:
        if event_service.reserve_tickets(event_id, item["type_id"], item["quantity"]):
            reserved.append(item)
        else:
            # Rollback reservas previas
            for prev in reserved:
                event_service.release_reservation(event_id, prev["type_id"], prev["quantity"])
            return "No hay suficientes entradas disponibles", 400

    session = stripe_service.create_checkout_session(
        event, buyer_name, buyer_email, items, attendee_names
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
        items = ticket_service.parse_items_from_metadata(metadata)

        event = event_service.get_event(event_id)
        if event and items:
            tickets = ticket_service.create_tickets(session, event, items)
            if tickets:
                for item in items:
                    event_service.confirm_reservation(event_id, item["type_id"], item["quantity"])

    elif stripe_event["type"] == "checkout.session.expired":
        session = stripe_event["data"]["object"]
        metadata = session.get("metadata", {})
        event_id = metadata.get("event_id")
        items = ticket_service.parse_items_from_metadata(metadata)

        if event_id:
            for item in items:
                event_service.release_reservation(event_id, item["type_id"], item["quantity"])

    return jsonify({"status": "ok"}), 200


@checkout_bp.route("/success")
def success():
    session_id = request.args.get("session_id", "")
    if not isinstance(session_id, str) or len(session_id) > 200:
        return render_template("success.html")

    if session_id:
        try:
            stripe.api_key = current_app.config["STRIPE_SECRET_KEY"]
            session = stripe.checkout.Session.retrieve(session_id)

            if session.payment_status == "paid":
                metadata = session.get("metadata", {})
                event_id = metadata.get("event_id")
                items = ticket_service.parse_items_from_metadata(metadata)

                event = event_service.get_event(event_id)
                if event and items:
                    tickets = ticket_service.create_tickets(session, event, items)
                    if tickets:
                        for item in items:
                            event_service.confirm_reservation(event_id, item["type_id"], item["quantity"])
        except Exception as e:
            current_app.logger.error(f"Error procesando pago en success: {e}")

    return render_template("success.html")


@checkout_bp.route("/cancel")
def cancel():
    return render_template("cancel.html")
