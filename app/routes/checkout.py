import stripe
from flask import Blueprint, request, redirect, render_template, jsonify, current_app
from app import limiter
from app.services import stripe_service, event_service, ticket_service
from app.utils.sanitize import clean, valid_uuid, valid_email, valid_int
from app.utils.csrf import csrf_protect

checkout_bp = Blueprint("checkout", __name__)


def _is_ajax():
    return request.headers.get("X-Requested-With") == "XMLHttpRequest"


def _error(message, status=400):
    if _is_ajax():
        return jsonify({"error": message}), status
    return message, status


@checkout_bp.route("/checkout/create-session", methods=["POST"])
@limiter.limit("10 per minute")
@csrf_protect
def create_session():
    event_id = valid_uuid(request.form.get("event_id"))
    buyer_first_name = clean(request.form.get("buyer_first_name", ""), max_length=100)
    buyer_last_name = clean(request.form.get("buyer_last_name", ""), max_length=100)
    buyer_name = f"{buyer_first_name} {buyer_last_name}"
    buyer_email = valid_email(request.form.get("buyer_email", ""))

    if not all([event_id, buyer_first_name, buyer_last_name, buyer_email]):
        return _error("Datos incompletos")

    event = event_service.get_event(event_id)
    if not event or event["status"] != "active":
        return _error("Evento no disponible", 404)

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
        return _error("Selecciona al menos una entrada")

    # Recoger nombres de asistentes
    attendee_names = []
    for i in range(1, total_quantity + 1):
        first = clean(request.form.get(f"attendee_first_name_{i}", ""), max_length=100)
        last = clean(request.form.get(f"attendee_last_name_{i}", ""), max_length=100)
        if not first or not last:
            return _error("Falta el nombre de algun asistente")
        attendee_names.append(f"{first} {last}")

    # Validar y consumir codigos de acceso antes de reservar
    consumed_codes = {}  # type_id -> [codes]
    for item in items:
        tt = event_service.get_ticket_type(event, item["type_id"])
        if tt and tt.get("access_codes_enabled"):
            if tt.get("access_codes_reusable"):
                # Reusable: single code per type
                code = clean(request.form.get(f"access_code_{item['type_id']}", ""), max_length=100)
                if not code:
                    _rollback_codes(event_id, event, consumed_codes)
                    return _error("Falta el codigo de acceso")
                codes_input = code
            else:
                # Non-reusable: one code per attendee of this type
                code_list = request.form.getlist(f"access_code_{item['type_id']}[]")
                code_list = [clean(c, max_length=100) for c in code_list]
                if len(code_list) != item["quantity"] or not all(code_list):
                    _rollback_codes(event_id, event, consumed_codes)
                    return _error("Falta el codigo de acceso")
                codes_input = code_list

            codes = event_service.validate_and_consume_access_codes(
                event_id, item["type_id"], codes_input
            )
            if codes is None:
                _rollback_codes(event_id, event, consumed_codes)
                return _error("Codigo de acceso no valido")
            consumed_codes[item["type_id"]] = codes

    # Reserva atomica por cada tipo
    reserved = []
    for item in items:
        if event_service.reserve_tickets(event_id, item["type_id"], item["quantity"]):
            reserved.append(item)
        else:
            # Rollback reservas previas
            for prev in reserved:
                event_service.release_reservation(event_id, prev["type_id"], prev["quantity"])
            _rollback_codes(event_id, event, consumed_codes)
            return _error("No hay suficientes entradas disponibles")

    session = stripe_service.create_checkout_session(
        event, buyer_name, buyer_email, items, attendee_names, consumed_codes
    )

    # Track reservations for stale cleanup
    for item in reserved:
        event_service.save_reservation(event_id, item["type_id"], item["quantity"], session.id)

    if _is_ajax():
        return jsonify({"redirect": session.url}), 200
    return redirect(session.url, code=303)


def _rollback_codes(event_id, event, consumed_codes):
    """Release any non-reusable access codes that were already consumed."""
    for prev_tid, prev_codes in consumed_codes.items():
        prev_tt = event_service.get_ticket_type(event, prev_tid)
        if prev_tt and not prev_tt.get("access_codes_reusable"):
            event_service.release_access_codes(event_id, prev_tid, prev_codes)


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
            event_service.delete_reservations_by_session(session.get("id"))

    elif stripe_event["type"] == "checkout.session.expired":
        session = stripe_event["data"]["object"]
        metadata = session.get("metadata", {})
        event_id = metadata.get("event_id")
        items = ticket_service.parse_items_from_metadata(metadata)

        if event_id:
            for item in items:
                event_service.release_reservation(event_id, item["type_id"], item["quantity"])

            # Release consumed access codes
            codes_by_type = ticket_service.parse_access_codes_from_metadata(metadata)
            for type_id, codes in codes_by_type.items():
                event_service.release_access_codes(event_id, type_id, codes)

            event_service.delete_reservations_by_session(session.get("id"))

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
                    event_service.delete_reservations_by_session(session_id)
        except Exception as e:
            current_app.logger.error(f"Error procesando pago en success: {e}")

    return render_template("success.html")


@checkout_bp.route("/cancel")
def cancel():
    return render_template("cancel.html")
