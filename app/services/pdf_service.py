import io
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader


def generate_pdf(ticket_data, event_data, qr_image_bytes):
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    # Titulo del evento
    c.setFont("Helvetica-Bold", 22)
    c.drawCentredString(width / 2, height - 60, event_data["name"])

    # Detalles del evento
    c.setFont("Helvetica", 12)
    y = height - 100
    c.drawString(50, y, f"Fecha: {event_data['date']}")
    y -= 20
    c.drawString(50, y, f"Lugar: {event_data['venue']}")
    y -= 30

    # Datos del comprador
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, y, "Datos de la entrada")
    y -= 25
    c.setFont("Helvetica", 12)
    c.drawString(50, y, f"Asistente: {ticket_data.get('attendee_name', ticket_data['buyer_name'])}")
    y -= 20
    c.drawString(50, y, f"Tipo: {ticket_data.get('ticket_type_name', 'General')}")
    y -= 20
    c.drawString(50, y, f"ID Entrada: {ticket_data['ticket_id']}")
    y -= 20
    c.drawString(50, y, f"Precio: {ticket_data['price']:.2f} {ticket_data['currency'].upper()}")
    y -= 40

    # QR
    qr_reader = ImageReader(io.BytesIO(qr_image_bytes))
    qr_size = 50 * mm
    c.drawImage(qr_reader, (width - qr_size) / 2, y - qr_size, qr_size, qr_size)

    c.save()
    buffer.seek(0)
    return buffer.getvalue()
