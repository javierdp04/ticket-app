"""Tests de las rutas del escaner QR."""
import json


class TestScannerAcceso:
    def test_scanner_evento_existente(self, client, created_event):
        response = client.get(f"/scanner/{created_event['event_id']}")
        assert response.status_code == 200
        assert b"Escaner" in response.data

    def test_scanner_evento_inexistente_404(self, client):
        response = client.get("/scanner/no-existe")
        assert response.status_code == 404


class TestScannerAuth:
    def test_pin_correcto_autentica(self, client, created_event):
        response = client.post("/scanner/auth", json={
            "event_id": created_event["event_id"],
            "pin": created_event["scanner_pin"],
        })
        data = json.loads(response.data)
        assert response.status_code == 200
        assert data["success"] is True

    def test_pin_incorrecto_rechaza(self, client, created_event):
        response = client.post("/scanner/auth", json={
            "event_id": created_event["event_id"],
            "pin": "000000",
        })
        data = json.loads(response.data)
        assert response.status_code == 401
        assert data["success"] is False


class TestScannerValidate:
    def _auth(self, client, event):
        """Helper: autentica al escaner con el PIN del evento."""
        client.post("/scanner/auth", json={
            "event_id": event["event_id"],
            "pin": event["scanner_pin"],
        })

    def test_sin_autenticar_devuelve_401(self, client, created_ticket):
        response = client.post("/scanner/validate", json={
            "ticket_id": created_ticket["ticket_id"],
            "event_id": created_ticket["event_id"],
        })
        assert response.status_code == 401

    def test_ticket_valido(self, client, created_event, created_ticket):
        self._auth(client, created_event)
        response = client.post("/scanner/validate", json={
            "ticket_id": created_ticket["ticket_id"],
            "event_id": created_event["event_id"],
        })
        data = json.loads(response.data)
        assert data["valid"] is True
        assert data["buyer_name"] == "Juan Test"

    def test_ticket_ya_usado(self, client, created_event, created_ticket):
        self._auth(client, created_event)
        # Primera validacion
        client.post("/scanner/validate", json={
            "ticket_id": created_ticket["ticket_id"],
            "event_id": created_event["event_id"],
        })
        # Segunda validacion - ya usado
        response = client.post("/scanner/validate", json={
            "ticket_id": created_ticket["ticket_id"],
            "event_id": created_event["event_id"],
        })
        data = json.loads(response.data)
        assert data["valid"] is False
        assert "ya usada" in data["reason"]

    def test_ticket_inexistente(self, client, created_event):
        self._auth(client, created_event)
        response = client.post("/scanner/validate", json={
            "ticket_id": "ticket-falso",
            "event_id": created_event["event_id"],
        })
        data = json.loads(response.data)
        assert data["valid"] is False

    def test_ticket_de_otro_evento(self, client, created_event, created_ticket, mock_db):
        from app.models.event import create_event
        other_event = create_event({
            "name": "Otro Evento",
            "date": "2026-12-01T20:00",
            "venue": "Otra Sala",
            "price": 10.00,
            "max_tickets": 50,
        })
        # Autenticar en el otro evento
        client.post("/scanner/auth", json={
            "event_id": other_event["event_id"],
            "pin": other_event["scanner_pin"],
        })
        # Intentar validar ticket del primer evento en el escaner del segundo
        response = client.post("/scanner/validate", json={
            "ticket_id": created_ticket["ticket_id"],
            "event_id": other_event["event_id"],
        })
        data = json.loads(response.data)
        assert data["valid"] is False
        assert "otro evento" in data["reason"]
