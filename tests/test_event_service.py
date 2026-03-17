"""Tests del servicio de eventos."""
import pytest
from app.services import event_service


class TestCreateEvent:
    def test_crea_evento_correctamente(self, app, mock_db):
        event = event_service.create_event({
            "name": "Festival",
            "date": "2026-09-01T18:00",
            "venue": "Parque Central",
            "price": 30.00,
            "max_tickets": 200,
        })
        assert event["name"] == "Festival"
        assert event["status"] == "active"
        assert event["tickets_sold"] == 0
        assert len(event["scanner_pin"]) == 6
        assert event["event_id"] is not None

    def test_evento_se_guarda_en_bd(self, app, mock_db):
        event = event_service.create_event({
            "name": "Gala",
            "date": "2026-10-01T20:00",
            "venue": "Hotel Lujo",
            "price": 50.00,
            "max_tickets": 100,
        })
        recovered = event_service.get_event(event["event_id"])
        assert recovered is not None
        assert recovered["name"] == "Gala"


class TestGetEvents:
    def test_get_active_events_solo_devuelve_activos(self, app, created_event, mock_db):
        from app.models.event import change_status, create_event
        paused = create_event({
            "name": "Evento Pausado",
            "date": "2026-12-01T20:00",
            "venue": "Sala B",
            "price": 10.00,
            "max_tickets": 50,
        })
        change_status(paused["event_id"], "paused")

        active_events = event_service.get_active_events()
        names = [e["name"] for e in active_events]
        assert "Evento Existente" in names
        assert "Evento Pausado" not in names

    def test_get_all_events_devuelve_todos(self, app, created_event, mock_db):
        from app.models.event import create_event, change_status
        finished = create_event({
            "name": "Evento Finalizado",
            "date": "2026-01-01T20:00",
            "venue": "Sala C",
            "price": 10.00,
            "max_tickets": 50,
        })
        change_status(finished["event_id"], "finished")

        all_events = event_service.get_all_events()
        assert len(all_events) >= 2


class TestAvailableTickets:
    def test_calcula_entradas_disponibles(self, app, created_event):
        available = event_service.get_available_tickets(created_event["event_id"])
        assert available == 50  # max_tickets=50, tickets_sold=0

    def test_devuelve_cero_si_evento_no_existe(self, app, mock_db):
        available = event_service.get_available_tickets("inexistente")
        assert available == 0

    def test_descuenta_entradas_vendidas(self, app, created_event, mock_db):
        from app.models.event import increment_tickets_sold
        increment_tickets_sold(created_event["event_id"], 10)
        available = event_service.get_available_tickets(created_event["event_id"])
        assert available == 40


class TestChangeStatus:
    def test_cambia_estado_a_paused(self, app, created_event):
        event_service.change_status(created_event["event_id"], "paused")
        event = event_service.get_event(created_event["event_id"])
        assert event["status"] == "paused"

    def test_cambia_estado_a_finished(self, app, created_event):
        event_service.change_status(created_event["event_id"], "finished")
        event = event_service.get_event(created_event["event_id"])
        assert event["status"] == "finished"

    def test_rechaza_estado_invalido(self, app, created_event):
        with pytest.raises(ValueError):
            event_service.change_status(created_event["event_id"], "borrado")


class TestUpdateEvent:
    def test_actualiza_nombre_y_precio(self, app, created_event):
        event_service.update_event(created_event["event_id"], {
            "name": "Nuevo Nombre",
            "price": 99.99,
        })
        event = event_service.get_event(created_event["event_id"])
        assert event["name"] == "Nuevo Nombre"
        assert event["price"] == 99.99

    def test_no_permite_campos_no_autorizados(self, app, created_event):
        event_service.update_event(created_event["event_id"], {
            "status": "finished",
            "scanner_pin": "000000",
            "name": "Actualizado",
        })
        event = event_service.get_event(created_event["event_id"])
        assert event["name"] == "Actualizado"
        # status y scanner_pin no deberian haber cambiado
        assert event["status"] == "active"
        assert event["scanner_pin"] != "000000"


class TestScannerPin:
    def test_pin_correcto_devuelve_true(self, app, created_event):
        pin = created_event["scanner_pin"]
        assert event_service.verify_scanner_pin(created_event["event_id"], pin) is True

    def test_pin_incorrecto_devuelve_false(self, app, created_event):
        assert event_service.verify_scanner_pin(created_event["event_id"], "999999") is False

    def test_evento_inexistente_devuelve_false(self, app, mock_db):
        assert event_service.verify_scanner_pin("no-existe", "123456") is False
