"""Tests de las rutas de checkout."""
from unittest.mock import patch, MagicMock


class TestCreateSession:
    def test_datos_incompletos_devuelve_400(self, client, created_event):
        response = client.post("/checkout/create-session", data={
            "event_id": created_event["event_id"],
            "buyer_name": "",
            "buyer_email": "test@test.com",
            "quantity": "1",
        })
        assert response.status_code == 400

    def test_evento_inexistente_devuelve_404(self, client):
        response = client.post("/checkout/create-session", data={
            "event_id": "no-existe",
            "buyer_name": "Test",
            "buyer_email": "test@test.com",
            "quantity": "1",
        })
        assert response.status_code == 404

    def test_evento_no_activo_devuelve_404(self, client, created_event):
        from app.models.event import change_status
        change_status(created_event["event_id"], "paused")
        response = client.post("/checkout/create-session", data={
            "event_id": created_event["event_id"],
            "buyer_name": "Test",
            "buyer_email": "test@test.com",
            "quantity": "1",
        })
        assert response.status_code == 404

    def test_cantidad_excede_aforo_devuelve_400(self, client, created_event):
        response = client.post("/checkout/create-session", data={
            "event_id": created_event["event_id"],
            "buyer_name": "Test",
            "buyer_email": "test@test.com",
            "quantity": "999",
        })
        assert response.status_code == 400

    @patch("app.routes.checkout.stripe_service.create_checkout_session")
    def test_datos_validos_redirige_a_stripe(self, mock_stripe, client, created_event):
        mock_session = MagicMock()
        mock_session.url = "https://checkout.stripe.com/test"
        mock_stripe.return_value = mock_session

        response = client.post("/checkout/create-session", data={
            "event_id": created_event["event_id"],
            "buyer_name": "Test User",
            "buyer_email": "test@test.com",
            "quantity": "2",
        })
        assert response.status_code == 303
        assert response.headers["Location"] == "https://checkout.stripe.com/test"
        mock_stripe.assert_called_once()


class TestWebhook:
    @patch("app.routes.checkout.stripe_service.verify_webhook")
    @patch("app.routes.checkout.ticket_service.create_tickets")
    def test_webhook_valido_crea_tickets(self, mock_create, mock_verify, client, created_event):
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
