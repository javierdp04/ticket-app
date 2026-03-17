import uuid

from app.models import ticket as ticket_model
from app.models import event as event_model
from app.services import qr_service, pdf_service, email_service


def create_tickets(stripe_session, event, quantity):
    order_id = str(uuid.uuid4())
    metadata = stripe_session.get("metadata", {})
    buyer_name = metadata.get("buyer_name", "")
    buyer_email = metadata.get("buyer_email", "")

    tickets = []
    pdf_list = []

    for _ in range(quantity):
        ticket = ticket_model.create_ticket({
            "event_id": event["event_id"],
            "order_id": order_id,
            "buyer_name": buyer_name,
            "buyer_email": buyer_email,
            "price": event["price"],
            "currency": event["currency"],
            "stripe_session_id": stripe_session.get("id"),
            "stripe_payment_intent": stripe_session.get("payment_intent"),
        })

        qr_bytes, qr_url = qr_service.generate_qr(ticket["ticket_id"])
        ticket_model.update_qr_code(ticket["ticket_id"], qr_url)

        pdf_bytes = pdf_service.generate_pdf(ticket, event, qr_bytes)
        pdf_list.append(pdf_bytes)
        tickets.append(ticket)

    event_model.increment_tickets_sold(event["event_id"], quantity)

    email_service.send_ticket_email(buyer_email, buyer_name, event, pdf_list)

    return tickets


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
        "ticket_id": ticket["ticket_id"],
    }


def get_event_stats(event_id):
    return ticket_model.get_event_stats(event_id)


def get_recent_purchases(event_id, limit=20):
    return ticket_model.get_recent_purchases(event_id, limit)
