from flask import Blueprint, abort, send_file
import io

from app.services import ticket_service, event_service
from app.services import qr_service, pdf_service

tickets_bp = Blueprint("tickets", __name__)


@tickets_bp.route("/ticket/<ticket_id>")
def download_ticket(ticket_id):
    ticket = ticket_service.get_ticket(ticket_id)
    if not ticket:
        abort(404)

    event = event_service.get_event(ticket["event_id"])
    if not event:
        abort(404)

    qr_bytes, _ = qr_service.generate_qr(ticket["ticket_id"])
    pdf_bytes = pdf_service.generate_pdf(ticket, event, qr_bytes)

    return send_file(
        io.BytesIO(pdf_bytes),
        mimetype="application/pdf",
        as_attachment=True,
        download_name=f"entrada_{ticket['ticket_id'][:8]}.pdf",
    )
