import uuid
import random
from datetime import datetime, timezone

from app import db


def create_event(data):
    ticket_types = []
    for tt in data.get("ticket_types", []):
        ticket_types.append({
            "type_id": tt.get("type_id") or uuid.uuid4().hex[:8],
            "name": tt["name"],
            "price": float(tt["price"]),
            "max_tickets": int(tt["max_tickets"]),
            "tickets_sold": 0,
            "tickets_reserved": 0,
        })

    event = {
        "event_id": str(uuid.uuid4()),
        "name": data["name"],
        "description": data.get("description", ""),
        "date": data["date"],
        "venue": data["venue"],
        "currency": data.get("currency", "eur"),
        "ticket_types": ticket_types,
        "status": "active",
        "image_filename": data.get("image_filename"),
        "scanner_pin": f"{random.randint(0, 999999):06d}",
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    db.events.insert_one(event)
    return event


def update_event(event_id, data):
    data["updated_at"] = datetime.now(timezone.utc)
    db.events.update_one({"event_id": event_id}, {"$set": data})


def change_status(event_id, new_status):
    db.events.update_one(
        {"event_id": event_id},
        {"$set": {"status": new_status, "updated_at": datetime.now(timezone.utc)}},
    )


def get_event(event_id):
    return db.events.find_one({"event_id": event_id})


def get_active_events():
    return list(db.events.find({"status": "active"}).sort("date", 1))


def get_all_events():
    return list(db.events.find().sort("created_at", -1))


def get_ticket_type(event, type_id):
    for tt in event.get("ticket_types", []):
        if tt["type_id"] == type_id:
            return tt
    return None


def reserve_tickets(event_id, ticket_type_id, quantity):
    """Atomically reserve tickets for a specific type using optimistic locking."""
    event = db.events.find_one({"event_id": event_id, "status": "active"})
    if not event:
        return False

    tt = get_ticket_type(event, ticket_type_id)
    if not tt:
        return False

    current_sold = tt["tickets_sold"]
    current_reserved = tt.get("tickets_reserved", 0)

    if current_sold + current_reserved + quantity > tt["max_tickets"]:
        return False

    result = db.events.update_one(
        {
            "event_id": event_id,
            "ticket_types.type_id": ticket_type_id,
            "ticket_types.tickets_sold": current_sold,
            "ticket_types.tickets_reserved": current_reserved,
        },
        {"$inc": {"ticket_types.$.tickets_reserved": quantity}},
    )
    return result.modified_count > 0


def confirm_reservation(event_id, ticket_type_id, quantity):
    """Convert a reservation into a confirmed sale for a specific type."""
    db.events.update_one(
        {"event_id": event_id, "ticket_types.type_id": ticket_type_id},
        {"$inc": {
            "ticket_types.$.tickets_reserved": -quantity,
            "ticket_types.$.tickets_sold": quantity,
        }},
    )


def release_reservation(event_id, ticket_type_id, quantity):
    """Release reserved tickets for a specific type."""
    db.events.update_one(
        {
            "event_id": event_id,
            "ticket_types.type_id": ticket_type_id,
            "ticket_types.tickets_reserved": {"$gte": quantity},
        },
        {"$inc": {"ticket_types.$.tickets_reserved": -quantity}},
    )
