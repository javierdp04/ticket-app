import json
import logging
import uuid

from app.models import ticket as ticket_model
from app.models import event as event_model
from app.services import qr_service, pdf_service, email_service

logger = logging.getLogger(__name__)


def create_tickets(stripe_session, event, items):
    """Create ticket records for multiple ticket types.

    items: list of {"type_id": str, "quantity": int}
    Does NOT modify event counters — the caller handles confirm_reservation.
    """
    session_id = stripe_session.get("id")
    if session_id and ticket_model.get_ticket_by_session(session_id):
        return []

    order_id = str(uuid.uuid4())
    metadata = stripe_session.get("metadata", {})
    buyer_name = metadata.get("buyer_name", "")
    buyer_email = metadata.get("buyer_email", "")

    attendee_names_raw = metadata.get("attendee_names", "")
    try:
        attendee_names = json.loads(attendee_names_raw)
    except (json.JSONDecodeError, TypeError):
        total_qty = sum(i["quantity"] for i in items)
        attendee_names = [buyer_name] * total_qty

    # Parse consumed access codes from metadata
    codes_by_type = parse_access_codes_from_metadata(metadata)

    tickets = []
    pdf_list = []
    attendee_idx = 0

    for item in items:
        type_id = item["type_id"]
        quantity = item["quantity"]
        tt = event_model.get_ticket_type(event, type_id)
        type_name = tt["name"] if tt else "General"
        price = tt["price"] if tt else 0
        type_codes = codes_by_type.get(type_id, [])
        reusable = tt.get("access_codes_reusable") if tt else False

        for j in range(quantity):
            attendee_name = attendee_names[attendee_idx] if attendee_idx < len(attendee_names) else buyer_name
            attendee_idx += 1

            # Determine which access code to record on this ticket
            access_code = ""
            if type_codes:
                if reusable:
                    access_code = type_codes[0]
                elif j < len(type_codes):
                    access_code = type_codes[j]

            ticket = ticket_model.create_ticket({
                "event_id": event["event_id"],
                "order_id": order_id,
                "buyer_name": buyer_name,
                "buyer_email": buyer_email,
                "attendee_name": attendee_name,
                "ticket_type_id": type_id,
                "ticket_type_name": type_name,
                "price": price,
                "currency": event["currency"],
                "stripe_session_id": session_id,
                "stripe_payment_intent": stripe_session.get("payment_intent"),
                "access_code_used": access_code,
            })

            qr_bytes, qr_url = qr_service.generate_qr(ticket["ticket_id"])
            ticket_model.update_qr_code(ticket["ticket_id"], qr_url)

            pdf_bytes = pdf_service.generate_pdf(ticket, event, qr_bytes)
            pdf_list.append(pdf_bytes)
            tickets.append(ticket)

    try:
        email_service.send_ticket_email(buyer_email, buyer_name, event, pdf_list)
        ticket_model.mark_email_sent(order_id)
    except Exception as e:
        logger.error("Error enviando email a %s (order %s): %s", buyer_email, order_id, e)

    return tickets


def parse_items_from_metadata(metadata):
    """Parse compact items JSON from Stripe metadata."""
    items_raw = metadata.get("items", "")
    try:
        compact = json.loads(items_raw)
        return [{"type_id": i["t"], "quantity": int(i["q"])} for i in compact]
    except (json.JSONDecodeError, TypeError, KeyError):
        return []


def parse_access_codes_from_metadata(metadata):
    """Parse consumed access codes from Stripe metadata.

    Returns dict mapping type_id to list of code strings.
    """
    raw = metadata.get("access_codes", "")
    if not raw:
        return {}
    try:
        entries = json.loads(raw)
        return {e["t"]: e["c"] for e in entries}
    except (json.JSONDecodeError, TypeError, KeyError):
        return {}


def get_ticket(ticket_id):
    return ticket_model.get_ticket(ticket_id)


def get_tickets_by_order(order_id):
    return ticket_model.get_tickets_by_order(order_id)


def validate_ticket(ticket_id):
    ticket = ticket_model.get_ticket(ticket_id)
    if not ticket:
        return {"valid": False, "reason": "Entrada no encontrada"}

    if ticket["status"] == "used":
        return {
            "valid": False,
            "reason": "Entrada ya usada",
            "used_at": str(ticket["used_at"]),
        }

    if ticket["status"] != "paid":
        return {"valid": False, "reason": "Entrada no valida"}

    ticket_model.mark_as_used(ticket_id)
    return {
        "valid": True,
        "buyer_name": ticket["buyer_name"],
        "attendee_name": ticket.get("attendee_name", ticket["buyer_name"]),
        "ticket_type": ticket.get("ticket_type_name", "General"),
        "ticket_id": ticket["ticket_id"],
    }


def get_event_stats(event_id):
    return ticket_model.get_event_stats(event_id)


def get_recent_purchases(event_id, limit=20):
    return ticket_model.get_recent_purchases(event_id, limit)
