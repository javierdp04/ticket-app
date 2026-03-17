from flask import render_template
from flask_mail import Message
from app import mail


def send_ticket_email(buyer_email, buyer_name, event_data, pdf_list):
    subject = f"Tus entradas para {event_data['name']}"
    quantity = len(pdf_list)
    body = (
        f"Hola {buyer_name},\n\n"
        f"Gracias por tu compra. Adjuntamos {'tu entrada' if quantity == 1 else f'tus {quantity} entradas'} "
        f"para {event_data['name']}.\n\n"
        f"Fecha: {event_data['date']}\n"
        f"Lugar: {event_data['venue']}\n\n"
        f"Presenta el codigo QR de cada entrada en la puerta del evento.\n\n"
        f"Un saludo."
    )

    html_body = render_template(
        "email/ticket_email.html",
        buyer_name=buyer_name,
        quantity=quantity,
        event_name=event_data["name"],
        event_date=event_data["date"],
        event_venue=event_data["venue"],
    )

    msg = Message(
        subject=subject,
        recipients=[buyer_email],
        body=body,
        html=html_body,
    )

    for i, pdf_bytes in enumerate(pdf_list, start=1):
        filename = f"entrada_{i}.pdf" if quantity > 1 else "entrada.pdf"
        msg.attach(filename, "application/pdf", pdf_bytes)

    mail.send(msg)
