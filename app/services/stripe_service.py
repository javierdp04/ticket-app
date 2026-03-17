import stripe
from flask import current_app


def create_checkout_session(event, buyer_name, buyer_email, quantity):
    stripe.api_key = current_app.config["STRIPE_SECRET_KEY"]
    base_url = current_app.config["BASE_URL"]

    session = stripe.checkout.Session.create(
        payment_method_types=["card"],
        line_items=[
            {
                "price_data": {
                    "currency": event["currency"],
                    "product_data": {
                        "name": f"Entrada - {event['name']}",
                    },
                    "unit_amount": int(event["price"] * 100),
                },
                "quantity": quantity,
            }
        ],
        mode="payment",
        success_url=f"{base_url}/success?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{base_url}/cancel",
        customer_email=buyer_email,
        metadata={
            "event_id": event["event_id"],
            "buyer_name": buyer_name,
            "buyer_email": buyer_email,
            "quantity": str(quantity),
        },
    )
    return session


def verify_webhook(payload, sig_header):
    webhook_secret = current_app.config["STRIPE_WEBHOOK_SECRET"]
    event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
    return event
