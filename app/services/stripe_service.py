import json
import stripe
from flask import current_app


def create_checkout_session(event, buyer_name, buyer_email, items, attendee_names,
                            consumed_codes=None):
    """Create a Stripe checkout session with multiple ticket types.

    items: list of {"type_id": str, "type_name": str, "quantity": int, "price": float}
    consumed_codes: dict mapping type_id to list of consumed code strings (optional)
    """
    stripe.api_key = current_app.config["STRIPE_SECRET_KEY"]
    base_url = current_app.config["BASE_URL"]

    line_items = []
    for item in items:
        line_items.append({
            "price_data": {
                "currency": event["currency"],
                "product_data": {
                    "name": f"{item['type_name']} - {event['name']}",
                },
                "unit_amount": int(item["price"] * 100),
            },
            "quantity": item["quantity"],
        })

    total_quantity = sum(i["quantity"] for i in items)

    # Compact items for metadata (Stripe has 500 char limit per value)
    items_meta = json.dumps([
        {"t": i["type_id"], "q": i["quantity"]} for i in items
    ])

    # Attendee names may exceed Stripe's 500-char metadata limit
    attendee_names_json = json.dumps(attendee_names)
    if len(attendee_names_json) > 490:
        attendee_names_json = ""  # fallback: ticket_service uses buyer_name

    # Access codes consumed during this session (for release on expiry)
    access_codes_json = ""
    if consumed_codes:
        access_codes_json = json.dumps([
            {"t": tid, "c": codes} for tid, codes in consumed_codes.items()
        ])
        if len(access_codes_json) > 490:
            access_codes_json = ""

    metadata = {
        "event_id": event["event_id"],
        "buyer_name": buyer_name,
        "buyer_email": buyer_email,
        "quantity": str(total_quantity),
        "items": items_meta,
        "attendee_names": attendee_names_json,
    }
    if access_codes_json:
        metadata["access_codes"] = access_codes_json

    session = stripe.checkout.Session.create(
        payment_method_types=["card"],
        line_items=line_items,
        mode="payment",
        success_url=f"{base_url}/success?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{base_url}/cancel",
        customer_email=buyer_email,
        metadata=metadata,
    )
    return session


def verify_webhook(payload, sig_header):
    webhook_secret = current_app.config["STRIPE_WEBHOOK_SECRET"]
    event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
    return event
