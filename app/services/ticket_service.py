import json
import uuid

from app.models import ticket as ticket_model
from app.models import event as event_model
from app.services import qr_service, pdf_service, email_service


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

    tickets = []
    pdf_list = []
    attendee_idx = 0

    for item in items:
        type_id = item["type_id"]
        quantity = item["quantity"]
        tt = event_model.get_ticket_type(event, type_id)
        type_name = tt["name"] if tt else "General"
        price = tt["price"] if tt else 0

        for _ in range(quantity):
            attendee_name = attendee_names[attendee_idx] if attendee_idx < len(attendee_names) else buyer_name
            attendee_idx += 1

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
            })

            qr_bytes, qr_url = qr_service.generate_qr(ticket["ticket_id"])
            ticket_model.update_qr_code(ticket["ticket_id"], qr_url)

            pdf_bytes = pdf_service.generate_pdf(ticket, event, qr_bytes)
            pdf_list.append(pdf_bytes)
            tickets.append(ticket)

    email_service.send_ticket_email(buyer_email, buyer_name, event, pdf_list)

    return tickets


def parse_items_from_metadata(metadata):
    """Parse compact items JSON from Stripe metadata."""
    items_raw = metadata.get("items", "")
    try:
        compact = json.loads(items_raw)
        return [{"type_id": i["t"], "quantity": int(i["q"])} for i in compact]
    except (json.JSONDecodeError, TypeError, KeyError):
        return []


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
