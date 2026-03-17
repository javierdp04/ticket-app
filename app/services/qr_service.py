import io
import qrcode
from flask import current_app


def generate_qr(ticket_id):
    base_url = current_app.config["BASE_URL"]
    validation_url = f"{base_url}/scanner/validate/{ticket_id}"

    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(validation_url)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)

    return buffer.getvalue(), validation_url
