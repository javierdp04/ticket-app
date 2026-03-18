import uuid
import random
from datetime import datetime, timedelta, timezone

from app import db


def create_event(data):
    ticket_types = []
    for tt in data.get("ticket_types", []):
        entry = {
            "type_id": tt.get("type_id") or uuid.uuid4().hex[:8],
            "name": tt["name"],
            "price": float(tt["price"]),
            "max_tickets": int(tt["max_tickets"]),
            "tickets_sold": 0,
            "tickets_reserved": 0,
        }
        if tt.get("access_codes_enabled"):
            entry["access_codes_enabled"] = True
            entry["access_codes_reusable"] = bool(tt.get("access_codes_reusable"))
            entry["access_codes"] = tt.get("access_codes", [])
        ticket_types.append(entry)

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


# --- Reservation tracking for stale cleanup ---

def save_reservation(event_id, type_id, quantity, stripe_session_id):
    """Track an individual reservation for cleanup purposes."""
    db.reservations.insert_one({
        "event_id": event_id,
        "type_id": type_id,
        "quantity": quantity,
        "stripe_session_id": stripe_session_id,
        "created_at": datetime.now(timezone.utc),
    })


def delete_reservations_by_session(stripe_session_id):
    """Delete all reservation records for a Stripe session."""
    return db.reservations.delete_many(
        {"stripe_session_id": stripe_session_id}
    ).deleted_count


def get_stale_reservations(max_age_minutes=35):
    """Find reservations older than max_age_minutes."""
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=max_age_minutes)
    return list(db.reservations.find({"created_at": {"$lt": cutoff}}))


def delete_reservation(reservation_id):
    """Atomically delete a single reservation. Returns True if deleted."""
    return db.reservations.delete_one({"_id": reservation_id}).deleted_count > 0


# --- Access codes ---

def validate_and_consume_access_codes(event_id, type_id, codes_input):
    """Validate and atomically consume access codes using optimistic locking.

    codes_input: a single code string for reusable types,
                 or a list of code strings (one per ticket) for single-use types.

    For reusable codes: verifies the code matches (no state change).
    For single-use codes: verifies each code exists and is unused, then marks
    them all as used atomically.

    Returns list of consumed code strings on success, None on failure.
    """
    event = db.events.find_one({"event_id": event_id})
    if not event:
        return None

    tt = get_ticket_type(event, type_id)
    if not tt or not tt.get("access_codes_enabled"):
        return None

    access_codes = tt.get("access_codes", [])

    if tt.get("access_codes_reusable"):
        code_upper = codes_input.strip().upper() if isinstance(codes_input, str) else codes_input[0].strip().upper()
        if not access_codes or access_codes[0]["code"] != code_upper:
            return None
        return [code_upper]

    # Non-reusable: codes_input must be a list of individual codes
    if isinstance(codes_input, str):
        codes_input = [codes_input]

    normalized = [c.strip().upper() for c in codes_input if c.strip()]
    if not normalized:
        return None

    # No duplicate codes in input
    if len(set(normalized)) != len(normalized):
        return None

    # Validate every code exists and is unused
    unused_set = {ac["code"] for ac in access_codes if not ac["used"]}
    for code in normalized:
        if code not in unused_set:
            return None

    to_consume_set = set(normalized)

    # Build new access_codes array with consumed codes marked
    new_access_codes = []
    for ac in access_codes:
        if ac["code"] in to_consume_set and not ac["used"]:
            new_access_codes.append({"code": ac["code"], "used": True})
        else:
            new_access_codes.append({"code": ac["code"], "used": ac["used"]})

    # Optimistic locking on current counters (same pattern as reserve_tickets)
    current_sold = tt["tickets_sold"]
    current_reserved = tt.get("tickets_reserved", 0)

    result = db.events.update_one(
        {
            "event_id": event_id,
            "ticket_types.type_id": type_id,
            "ticket_types.tickets_sold": current_sold,
            "ticket_types.tickets_reserved": current_reserved,
        },
        {"$set": {"ticket_types.$.access_codes": new_access_codes}},
    )
    if result.modified_count > 0:
        return list(normalized)
    return None


def release_access_codes(event_id, type_id, codes):
    """Release previously consumed access codes (set used back to False)."""
    if not codes:
        return

    event = db.events.find_one({"event_id": event_id})
    if not event:
        return

    tt = get_ticket_type(event, type_id)
    if not tt:
        return

    access_codes = tt.get("access_codes", [])
    codes_set = {c.upper() for c in codes}

    new_access_codes = []
    for ac in access_codes:
        if ac["code"] in codes_set and ac["used"]:
            new_access_codes.append({"code": ac["code"], "used": False})
        else:
            new_access_codes.append({"code": ac["code"], "used": ac["used"]})

    db.events.update_one(
        {"event_id": event_id, "ticket_types.type_id": type_id},
        {"$set": {"ticket_types.$.access_codes": new_access_codes}},
    )
