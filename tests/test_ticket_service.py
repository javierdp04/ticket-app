"""Tests del servicio de tickets."""
from unittest.mock import patch
from app.services import ticket_service
from app.models.ticket import create_ticket, mark_as_used


class TestValidateTicket:
    def test_valida_ticket_pagado(self, app, created_ticket):
        result = ticket_service.validate_ticket(created_ticket["ticket_id"])
        assert result["valid"] is True
        assert result["buyer_name"] == "Juan Test"

    def test_rechaza_ticket_ya_usado(self, app, created_ticket):
        mark_as_used(created_ticket["ticket_id"])
        result = ticket_service.validate_ticket(created_ticket["ticket_id"])
        assert result["valid"] is False
        assert "ya usada" in result["reason"]
        assert "used_at" in result

    def test_rechaza_ticket_inexistente(self, app, mock_db):
        result = ticket_service.validate_ticket("ticket-falso")
        assert result["valid"] is False
        assert "no encontrada" in result["reason"]

    def test_no_se_puede_usar_dos_veces(self, app, created_ticket):
        r1 = ticket_service.validate_ticket(created_ticket["ticket_id"])
        r2 = ticket_service.validate_ticket(created_ticket["ticket_id"])
        assert r1["valid"] is True
        assert r2["valid"] is False


class TestCreateTickets:
    @patch("app.services.ticket_service.email_service.send_ticket_email")
    @patch("app.services.ticket_service.pdf_service.generate_pdf", return_value=b"%PDF-fake")
    @patch("app.services.ticket_service.qr_service.generate_qr", return_value=(b"qr-bytes", "http://url"))
    def test_crea_multiples_tickets(self, mock_qr, mock_pdf, mock_email, app, created_event):
        tt = created_event["ticket_types"][0]
        stripe_session = {
            "id": "cs_test_999",
            "payment_intent": "pi_test_999",
            "metadata": {
                "event_id": created_event["event_id"],
                "buyer_name": "Maria Test",
                "buyer_email": "maria@test.com",
                "quantity": "3",
                "attendee_names": '["Maria Test", "Maria Test", "Maria Test"]',
            },
        }
        items = [{"type_id": tt["type_id"], "quantity": 3}]
        tickets = ticket_service.create_tickets(stripe_session, created_event, items)

        assert len(tickets) == 3
        # Todos comparten order_id
        order_ids = {t["order_id"] for t in tickets}
        assert len(order_ids) == 1
        # Todos tienen el event_id correcto
        for t in tickets:
            assert t["event_id"] == created_event["event_id"]
            assert t["status"] == "paid"
            assert t["buyer_name"] == "Maria Test"
            assert t["ticket_type_name"] == "General"

    @patch("app.services.ticket_service.email_service.send_ticket_email")
    @patch("app.services.ticket_service.pdf_service.generate_pdf", return_value=b"%PDF-fake")
    @patch("app.services.ticket_service.qr_service.generate_qr", return_value=(b"qr-bytes", "http://url"))
    def test_confirm_reservation_incrementa_tickets_sold(self, mock_qr, mock_pdf, mock_email, app, created_event):
        """create_tickets no incrementa tickets_sold directamente;
        el caller debe usar confirm_reservation para eso."""
        from app.services import event_service

        event_id = created_event["event_id"]
        tt = created_event["ticket_types"][0]
        type_id = tt["type_id"]

        # Reservar + crear tickets + confirmar (flujo completo)
        event_service.reserve_tickets(event_id, type_id, 2)
        stripe_session = {
            "id": "cs_test_888",
            "payment_intent": "pi_test_888",
            "metadata": {
                "event_id": event_id,
                "buyer_name": "Pedro Test",
                "buyer_email": "pedro@test.com",
                "quantity": "2",
                "attendee_names": '["Pedro Test", "Pedro Test"]',
            },
        }
        items = [{"type_id": type_id, "quantity": 2}]
        ticket_service.create_tickets(stripe_session, created_event, items)
        event_service.confirm_reservation(event_id, type_id, 2)

        event = event_service.get_event(event_id)
        assert event["ticket_types"][0]["tickets_sold"] == 2
        assert event["ticket_types"][0].get("tickets_reserved", 0) == 0

    @patch("app.services.ticket_service.email_service.send_ticket_email")
    @patch("app.services.ticket_service.pdf_service.generate_pdf", return_value=b"%PDF-fake")
    @patch("app.services.ticket_service.qr_service.generate_qr", return_value=(b"qr-bytes", "http://url"))
    def test_envia_email_con_todos_los_pdfs(self, mock_qr, mock_pdf, mock_email, app, created_event):
        tt = created_event["ticket_types"][0]
        stripe_session = {
            "id": "cs_test_777",
            "payment_intent": "pi_test_777",
            "metadata": {
                "event_id": created_event["event_id"],
                "buyer_name": "Ana Test",
                "buyer_email": "ana@test.com",
                "quantity": "2",
                "attendee_names": '["Ana Test", "Ana Test"]',
            },
        }
        items = [{"type_id": tt["type_id"], "quantity": 2}]
        ticket_service.create_tickets(stripe_session, created_event, items)
        mock_email.assert_called_once()
        args = mock_email.call_args
        pdf_list = args[0][3]  # 4to argumento posicional
        assert len(pdf_list) == 2


class TestGetTicket:
    def test_recupera_ticket_existente(self, app, created_ticket):
        ticket = ticket_service.get_ticket(created_ticket["ticket_id"])
        assert ticket is not None
        assert ticket["buyer_email"] == "juan@test.com"

    def test_devuelve_none_si_no_existe(self, app, mock_db):
        ticket = ticket_service.get_ticket("no-existe")
        assert ticket is None


class TestGetTicketsByOrder:
    def test_agrupa_tickets_por_order(self, app, mock_db, created_event):
        t1 = create_ticket({
            "event_id": created_event["event_id"],
            "order_id": "order-abc",
            "buyer_name": "Test",
            "buyer_email": "test@test.com",
            "price": 10.0,
        })
        t2 = create_ticket({
            "event_id": created_event["event_id"],
            "order_id": "order-abc",
            "buyer_name": "Test",
            "buyer_email": "test@test.com",
            "price": 10.0,
        })
        create_ticket({
            "event_id": created_event["event_id"],
            "order_id": "order-otro",
            "buyer_name": "Otro",
            "buyer_email": "otro@test.com",
            "price": 10.0,
        })

        tickets = ticket_service.get_tickets_by_order("order-abc")
        assert len(tickets) == 2


class TestEventStats:
    def test_stats_con_tickets_mixtos(self, app, mock_db, created_event):
        for i in range(3):
            create_ticket({
                "event_id": created_event["event_id"],
                "order_id": f"order-{i}",
                "buyer_name": f"Comprador {i}",
                "buyer_email": f"buyer{i}@test.com",
                "price": 25.0,
            })
        # Marcar uno como usado
        tickets = ticket_service.get_tickets_by_order("order-0")
        mark_as_used(tickets[0]["ticket_id"])

        stats = ticket_service.get_event_stats(created_event["event_id"])
        assert stats["total_sold"] == 3
        assert stats["used"] == 1
        assert stats["paid"] == 2
        assert stats["total_revenue"] == 75.0
