import uuid
import random
from datetime import datetime, timezone

from app import db


def create_event(data):
    event = {
        "event_id": str(uuid.uuid4()),
        "name": data["name"],
        "description": data.get("description", ""),
        "date": data["date"],
        "venue": data["venue"],
        "price": float(data["price"]),
        "currency": data.get("currency", "eur"),
        "max_tickets": int(data["max_tickets"]),
        "tickets_sold": 0,
        "status": "active",
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


def increment_tickets_sold(event_id, quantity):
    db.events.update_one(
        {"event_id": event_id},
        {"$inc": {"tickets_sold": quantity}},
    )
