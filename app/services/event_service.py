import os
import uuid

from werkzeug.utils import secure_filename

from app.models import event as event_model

UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static", "uploads", "events")
ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}
ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_IMAGE_SIZE = 5 * 1024 * 1024  # 5 MB


def _allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def save_image(file):
    """Valida y guarda una imagen subida. Devuelve el nombre de archivo generado."""
    if not file or not file.filename:
        return None

    if not _allowed_file(file.filename):
        raise ValueError("Formato de imagen no permitido. Usa JPG, PNG o WEBP.")

    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise ValueError("Tipo de contenido no permitido.")

    file.seek(0, os.SEEK_END)
    size = file.tell()
    file.seek(0)
    if size > MAX_IMAGE_SIZE:
        raise ValueError("La imagen supera el tamaño maximo de 5 MB.")

    ext = secure_filename(file.filename).rsplit(".", 1)[1].lower()
    filename = f"{uuid.uuid4().hex}.{ext}"

    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    file.save(os.path.join(UPLOAD_FOLDER, filename))
    return filename


def delete_image(filename):
    """Elimina una imagen del disco si existe."""
    if not filename:
        return
    path = os.path.join(UPLOAD_FOLDER, filename)
    if os.path.isfile(path):
        os.remove(path)


def create_event(data):
    return event_model.create_event(data)


def update_event(event_id, data):
    allowed_fields = ["name", "description", "date", "venue", "currency", "ticket_types", "image_filename"]
    filtered = {k: v for k, v in data.items() if k in allowed_fields}
    event_model.update_event(event_id, filtered)


def change_status(event_id, new_status):
    valid_statuses = ("active", "paused", "finished")
    if new_status not in valid_statuses:
        raise ValueError(f"Estado no valido: {new_status}")
    event_model.change_status(event_id, new_status)


def get_event(event_id):
    return event_model.get_event(event_id)


def get_active_events():
    return event_model.get_active_events()


def get_all_events():
    return event_model.get_all_events()


def get_ticket_type(event, type_id):
    return event_model.get_ticket_type(event, type_id)


def get_total_capacity(event):
    return sum(tt["max_tickets"] for tt in event.get("ticket_types", []))


def get_total_sold(event):
    return sum(tt["tickets_sold"] for tt in event.get("ticket_types", []))


def get_total_available(event):
    total = 0
    for tt in event.get("ticket_types", []):
        total += tt["max_tickets"] - tt["tickets_sold"] - tt.get("tickets_reserved", 0)
    return total


def get_available_tickets(event_id):
    event = event_model.get_event(event_id)
    if not event:
        return 0
    return get_total_available(event)


def reserve_tickets(event_id, ticket_type_id, quantity):
    return event_model.reserve_tickets(event_id, ticket_type_id, quantity)


def confirm_reservation(event_id, ticket_type_id, quantity):
    event_model.confirm_reservation(event_id, ticket_type_id, quantity)


def release_reservation(event_id, ticket_type_id, quantity):
    event_model.release_reservation(event_id, ticket_type_id, quantity)


def save_reservation(event_id, type_id, quantity, stripe_session_id):
    event_model.save_reservation(event_id, type_id, quantity, stripe_session_id)


def delete_reservations_by_session(stripe_session_id):
    return event_model.delete_reservations_by_session(stripe_session_id)


def cleanup_stale_reservations(max_age_minutes=35):
    """Release reservations older than max_age_minutes (Stripe default expiry is 30 min)."""
    stale = event_model.get_stale_reservations(max_age_minutes)
    released = 0
    for r in stale:
        # Atomic delete ensures only one process releases each reservation
        if event_model.delete_reservation(r["_id"]):
            event_model.release_reservation(r["event_id"], r["type_id"], r["quantity"])
            released += 1
    return released


def validate_and_consume_access_codes(event_id, type_id, codes_input):
    return event_model.validate_and_consume_access_codes(event_id, type_id, codes_input)


def release_access_codes(event_id, type_id, codes):
    event_model.release_access_codes(event_id, type_id, codes)


def verify_scanner_pin(event_id, pin):
    event = event_model.get_event(event_id)
    if not event:
        return False
    return str(event.get("scanner_pin", "")) == str(pin)
