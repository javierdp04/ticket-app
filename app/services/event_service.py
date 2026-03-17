from app.models import event as event_model


def create_event(data):
    return event_model.create_event(data)


def update_event(event_id, data):
    allowed_fields = ["name", "description", "date", "venue", "price", "currency", "max_tickets"]
    filtered = {k: v for k, v in data.items() if k in allowed_fields}
    if "price" in filtered:
        filtered["price"] = float(filtered["price"])
    if "max_tickets" in filtered:
        filtered["max_tickets"] = int(filtered["max_tickets"])
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


def get_available_tickets(event_id):
    event = event_model.get_event(event_id)
    if not event:
        return 0
    return event["max_tickets"] - event["tickets_sold"]


def verify_scanner_pin(event_id, pin):
    event = event_model.get_event(event_id)
    if not event:
        return False
    return event["scanner_pin"] == pin
