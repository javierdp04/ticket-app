import uuid
from datetime import datetime, timezone

from app import db


def create_ticket(data):
    ticket = {
        "ticket_id": str(uuid.uuid4()),
        "event_id": data["event_id"],
        "order_id": data["order_id"],
        "buyer_name": data["buyer_name"],
        "buyer_email": data["buyer_email"],
        "price": float(data["price"]),
        "currency": data.get("currency", "eur"),
        "stripe_session_id": data.get("stripe_session_id"),
        "stripe_payment_intent": data.get("stripe_payment_intent"),
        "status": "paid",
        "qr_code": "",
        "created_at": datetime.now(timezone.utc),
        "used_at": None,
    }
    db.tickets.insert_one(ticket)
    return ticket


def get_ticket(ticket_id):
    return db.tickets.find_one({"ticket_id": ticket_id})


def get_tickets_by_order(order_id):
    return list(db.tickets.find({"order_id": order_id}))


def get_tickets_by_event(event_id):
    return list(db.tickets.find({"event_id": event_id}))


def mark_as_used(ticket_id):
    db.tickets.update_one(
        {"ticket_id": ticket_id},
        {"$set": {"status": "used", "used_at": datetime.now(timezone.utc)}},
    )


def update_qr_code(ticket_id, qr_url):
    db.tickets.update_one(
        {"ticket_id": ticket_id},
        {"$set": {"qr_code": qr_url}},
    )


def get_event_stats(event_id):
    pipeline = [
        {"$match": {"event_id": event_id}},
        {
            "$group": {
                "_id": "$status",
                "count": {"$sum": 1},
                "revenue": {"$sum": "$price"},
            }
        },
    ]
    results = list(db.tickets.aggregate(pipeline))

    stats = {"paid": 0, "used": 0, "cancelled": 0, "total_revenue": 0.0}
    for r in results:
        stats[r["_id"]] = r["count"]
        if r["_id"] in ("paid", "used"):
            stats["total_revenue"] += r["revenue"]

    stats["total_sold"] = stats["paid"] + stats["used"]
    return stats


def get_recent_purchases(event_id, limit=20):
    return list(
        db.tickets.find({"event_id": event_id, "status": {"$in": ["paid", "used"]}})
        .sort("created_at", -1)
        .limit(limit)
    )
