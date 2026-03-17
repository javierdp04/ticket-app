"""Tests de los servicios de generacion de PDF y QR."""
from app.services import qr_service, pdf_service


class TestQRService:
    def test_genera_qr_como_bytes(self, app):
        with app.app_context():
            qr_bytes, url = qr_service.generate_qr("ticket-123")
            assert isinstance(qr_bytes, bytes)
            assert len(qr_bytes) > 0

    def test_qr_contiene_url_de_validacion(self, app):
        with app.app_context():
            _, url = qr_service.generate_qr("ticket-abc")
            assert "scanner/validate/ticket-abc" in url

    def test_qr_usa_base_url_configurada(self, app):
        with app.app_context():
            _, url = qr_service.generate_qr("t-1")
            assert url.startswith("http://localhost:5000")


class TestPDFService:
    def test_genera_pdf_como_bytes(self, app):
        ticket = {
            "ticket_id": "tid-123",
            "buyer_name": "Test User",
            "price": 25.00,
            "currency": "eur",
        }
        event = {
            "name": "Evento PDF",
            "date": "2026-07-01T20:00",
            "venue": "Sala PDF",
        }
        with app.app_context():
            qr_bytes, _ = qr_service.generate_qr("tid-123")
            pdf_bytes = pdf_service.generate_pdf(ticket, event, qr_bytes)

        assert isinstance(pdf_bytes, bytes)
        assert pdf_bytes[:5] == b"%PDF-"
        assert len(pdf_bytes) > 100
