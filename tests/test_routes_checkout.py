"""Tests de las rutas de checkout."""
import json
from unittest.mock import patch, MagicMock


class TestCreateSession:
    def test_datos_incompletos_devuelve_400(self, client, created_event):
        tt = created_event["ticket_types"][0]
        response = client.post("/checkout/create-session", data={
            "event_id": created_event["event_id"],
            "buyer_first_name": "",
            "buyer_last_name": "",
            "buyer_email": "test@test.com",
            f"quantity_{tt['type_id']}": "1",
        })
        assert response.status_code == 400

    def test_evento_inexistente_devuelve_400(self, client):
        """Un event_id que no es UUID valido se rechaza como datos incompletos."""
        response = client.post("/checkout/create-session", data={
            "event_id": "no-existe",
            "buyer_first_name": "Test",
            "buyer_last_name": "User",
            "buyer_email": "test@test.com",
        })
        assert response.status_code == 400

    def test_evento_no_activo_no_reserva(self, client, created_event):
        from app.models.event import change_status
        change_status(created_event["event_id"], "paused")
        tt = created_event["ticket_types"][0]
        response = client.post("/checkout/create-session", data={
            "event_id": created_event["event_id"],
            "buyer_first_name": "Test",
            "buyer_last_name": "User",
            "buyer_email": "test@test.com",
            f"quantity_{tt['type_id']}": "1",
            "attendee_first_name_1": "Test",
            "attendee_last_name_1": "User",
        })
        assert response.status_code == 404

    def test_cantidad_excede_aforo_devuelve_400(self, client, created_event):
        tt = created_event["ticket_types"][0]
        response = client.post("/checkout/create-session", data={
            "event_id": created_event["event_id"],
            "buyer_first_name": "Test",
            "buyer_last_name": "User",
            "buyer_email": "test@test.com",
            f"quantity_{tt['type_id']}": "999",
            "attendee_first_name_1": "Test",
            "attendee_last_name_1": "User",
        })
        assert response.status_code == 400

    @patch("app.routes.checkout.stripe_service.create_checkout_session")
    def test_datos_validos_redirige_a_stripe(self, mock_stripe, client, created_event):
        mock_session = MagicMock()
        mock_session.url = "https://checkout.stripe.com/test"
        mock_session.id = "cs_test_123"
        mock_stripe.return_value = mock_session

        tt = created_event["ticket_types"][0]
        response = client.post("/checkout/create-session", data={
            "event_id": created_event["event_id"],
            "buyer_first_name": "Test",
            "buyer_last_name": "User",
            "buyer_email": "test@test.com",
            f"quantity_{tt['type_id']}": "2",
            "attendee_first_name_1": "Test",
            "attendee_last_name_1": "User",
            "attendee_first_name_2": "Other",
            "attendee_last_name_2": "Person",
        })
        assert response.status_code == 303
        assert response.headers["Location"] == "https://checkout.stripe.com/test"
        mock_stripe.assert_called_once()


class TestWebhook:
    @patch("app.routes.checkout.stripe_service.verify_webhook")
    @patch("app.routes.checkout.ticket_service.create_tickets", return_value=[{"id": "t1"}])
    def test_webhook_valido_crea_tickets(self, mock_create, mock_verify, client, created_event):
        tt = created_event["ticket_types"][0]
        items_meta = json.dumps([{"t": tt["type_id"], "q": 2}])
        mock_verify.return_value = {
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": "cs_test_123",
                    "payment_intent": "pi_test_123",
                    "metadata": {
                        "event_id": created_event["event_id"],
                        "buyer_name": "Webhook User",
                        "buyer_email": "webhook@test.com",
                        "quantity": "2",
                        "items": items_meta,
                    },
                }
            },
        }
        response = client.post(
            "/checkout/webhook",
            data=b"payload",
            headers={"Stripe-Signature": "sig_test"},
        )
        assert response.status_code == 200
        mock_create.assert_called_once()

    @patch("app.routes.checkout.stripe_service.verify_webhook", side_effect=Exception("Invalid"))
    def test_webhook_firma_invalida_devuelve_400(self, mock_verify, client):
        response = client.post(
            "/checkout/webhook",
            data=b"payload",
            headers={"Stripe-Signature": "sig_bad"},
        )
        assert response.status_code == 400

    @patch("app.routes.checkout.stripe_service.verify_webhook")
    def test_webhook_ignora_otros_eventos(self, mock_verify, client):
        mock_verify.return_value = {
            "type": "payment_intent.created",
            "data": {"object": {}},
        }
        response = client.post(
            "/checkout/webhook",
            data=b"payload",
            headers={"Stripe-Signature": "sig_test"},
        )
        assert response.status_code == 200
