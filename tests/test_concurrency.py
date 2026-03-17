"""Tests de concurrencia para verificar que el sistema de reservas
previene sobreventa bajo carga simultanea."""

import threading
import uuid
from unittest.mock import patch

import mongomock
import pytest

TYPE_ID = "gen1"


@pytest.fixture
def mock_db():
    client = mongomock.MongoClient()
    return client["testdb"]


@pytest.fixture
def app(mock_db):
    with patch("app.MongoClient") as mock_client:
        mock_client.return_value.get_default_database.return_value = mock_db

        from app import create_app
        application = create_app()
        application.config["TESTING"] = True
        application.config["BASE_URL"] = "https://localhost:5000"

        # Patch db in all modules that import it at module level
        import app as app_module
        app_module.db = mock_db

        from app.models import event as event_mod
        from app.models import ticket as ticket_mod
        event_mod.db = mock_db
        ticket_mod.db = mock_db

        yield application


def _create_test_event(db, max_tickets=10):
    event_id = str(uuid.uuid4())
    db.events.insert_one({
        "event_id": event_id,
        "name": "Test Event",
        "description": "",
        "date": "2026-06-01",
        "venue": "Test Venue",
        "currency": "eur",
        "ticket_types": [{
            "type_id": TYPE_ID,
            "name": "General",
            "price": 10.0,
            "max_tickets": max_tickets,
            "tickets_sold": 0,
            "tickets_reserved": 0,
        }],
        "status": "active",
        "scanner_pin": "123456",
    })
    return event_id


class TestAtomicReservation:

    def test_reserve_within_limit(self, app, mock_db):
        with app.app_context():
            from app.models import event as event_model
            event_id = _create_test_event(mock_db, max_tickets=10)

            assert event_model.reserve_tickets(event_id, TYPE_ID, 5) is True

            event = mock_db.events.find_one({"event_id": event_id})
            assert event["ticket_types"][0]["tickets_reserved"] == 5

    def test_reserve_exact_limit(self, app, mock_db):
        with app.app_context():
            from app.models import event as event_model
            event_id = _create_test_event(mock_db, max_tickets=5)

            assert event_model.reserve_tickets(event_id, TYPE_ID, 5) is True

            event = mock_db.events.find_one({"event_id": event_id})
            assert event["ticket_types"][0]["tickets_reserved"] == 5

    def test_reserve_over_limit_rejected(self, app, mock_db):
        with app.app_context():
            from app.models import event as event_model
            event_id = _create_test_event(mock_db, max_tickets=5)

            assert event_model.reserve_tickets(event_id, TYPE_ID, 6) is False

            event = mock_db.events.find_one({"event_id": event_id})
            assert event["ticket_types"][0]["tickets_reserved"] == 0

    def test_reserve_accounts_for_sold(self, app, mock_db):
        with app.app_context():
            from app.models import event as event_model
            event_id = _create_test_event(mock_db, max_tickets=10)

            mock_db.events.update_one(
                {"event_id": event_id, "ticket_types.type_id": TYPE_ID},
                {"$set": {"ticket_types.$.tickets_sold": 8}}
            )

            assert event_model.reserve_tickets(event_id, TYPE_ID, 2) is True
            assert event_model.reserve_tickets(event_id, TYPE_ID, 1) is False

    def test_reserve_accounts_for_existing_reservations(self, app, mock_db):
        with app.app_context():
            from app.models import event as event_model
            event_id = _create_test_event(mock_db, max_tickets=10)

            assert event_model.reserve_tickets(event_id, TYPE_ID, 7) is True
            assert event_model.reserve_tickets(event_id, TYPE_ID, 4) is False
            assert event_model.reserve_tickets(event_id, TYPE_ID, 3) is True

            event = mock_db.events.find_one({"event_id": event_id})
            assert event["ticket_types"][0]["tickets_reserved"] == 10

    def test_reserve_inactive_event_rejected(self, app, mock_db):
        with app.app_context():
            from app.models import event as event_model
            event_id = _create_test_event(mock_db, max_tickets=100)

            mock_db.events.update_one(
                {"event_id": event_id},
                {"$set": {"status": "paused"}}
            )

            assert event_model.reserve_tickets(event_id, TYPE_ID, 1) is False


class TestConfirmAndRelease:

    def test_confirm_converts_reserved_to_sold(self, app, mock_db):
        with app.app_context():
            from app.models import event as event_model
            event_id = _create_test_event(mock_db, max_tickets=10)

            event_model.reserve_tickets(event_id, TYPE_ID, 3)
            event_model.confirm_reservation(event_id, TYPE_ID, 3)

            event = mock_db.events.find_one({"event_id": event_id})
            assert event["ticket_types"][0]["tickets_reserved"] == 0
            assert event["ticket_types"][0]["tickets_sold"] == 3

    def test_release_frees_reserved(self, app, mock_db):
        with app.app_context():
            from app.models import event as event_model
            event_id = _create_test_event(mock_db, max_tickets=10)

            event_model.reserve_tickets(event_id, TYPE_ID, 5)
            event_model.release_reservation(event_id, TYPE_ID, 5)

            event = mock_db.events.find_one({"event_id": event_id})
            assert event["ticket_types"][0]["tickets_reserved"] == 0
            assert event["ticket_types"][0]["tickets_sold"] == 0

    def test_release_then_reserve_again(self, app, mock_db):
        with app.app_context():
            from app.models import event as event_model
            event_id = _create_test_event(mock_db, max_tickets=5)

            assert event_model.reserve_tickets(event_id, TYPE_ID, 5) is True
            assert event_model.reserve_tickets(event_id, TYPE_ID, 1) is False

            event_model.release_reservation(event_id, TYPE_ID, 5)

            assert event_model.reserve_tickets(event_id, TYPE_ID, 5) is True


class TestAvailableTickets:

    def test_available_accounts_for_reservations(self, app, mock_db):
        with app.app_context():
            from app.services import event_service
            event_id = _create_test_event(mock_db, max_tickets=100)

            mock_db.events.update_one(
                {"event_id": event_id, "ticket_types.type_id": TYPE_ID},
                {"$set": {
                    "ticket_types.$.tickets_sold": 30,
                    "ticket_types.$.tickets_reserved": 20,
                }}
            )

            assert event_service.get_available_tickets(event_id) == 50


class TestTicketCreationIdempotency:

    def test_duplicate_session_skipped(self, app, mock_db):
        with app.app_context():
            from app.services import ticket_service

            session_id = "cs_test_123"

            mock_db.tickets.insert_one({
                "ticket_id": str(uuid.uuid4()),
                "event_id": "evt1",
                "stripe_session_id": session_id,
                "status": "paid",
            })

            fake_session = {"id": session_id, "metadata": {
                "buyer_name": "Test", "buyer_email": "t@t.com",
                "attendee_names": '["Test"]',
            }}
            fake_event = {
                "event_id": "evt1",
                "currency": "eur",
                "ticket_types": [{"type_id": "gen1", "name": "General", "price": 10, "max_tickets": 100, "tickets_sold": 0, "tickets_reserved": 0}],
            }

            result = ticket_service.create_tickets(
                fake_session, fake_event,
                [{"type_id": "gen1", "quantity": 1}],
            )
            assert result == []


class TestConcurrentReservations:

    def test_concurrent_reservations_no_oversell(self, app, mock_db):
        """Con 10 tickets y 20 usuarios intentando reservar 1,
        solo 10 deben tener exito."""
        with app.app_context():
            from app.models import event as event_model
            event_id = _create_test_event(mock_db, max_tickets=10)

            results = []
            barrier = threading.Barrier(20)

            def try_reserve():
                barrier.wait()
                ok = event_model.reserve_tickets(event_id, TYPE_ID, 1)
                results.append(ok)

            threads = [threading.Thread(target=try_reserve) for _ in range(20)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            successes = sum(1 for r in results if r)
            event = mock_db.events.find_one({"event_id": event_id})

            assert successes == 10
            assert event["ticket_types"][0]["tickets_reserved"] == 10
            assert event["ticket_types"][0]["tickets_sold"] == 0

    def test_1000_ticket_event_200_buyers(self, app, mock_db):
        """Un evento de 1000 entradas, 250 compradores de 5 entradas cada uno.
        Solo 200 deben tener exito (200*5=1000)."""
        with app.app_context():
            from app.models import event as event_model
            event_id = _create_test_event(mock_db, max_tickets=1000)

            results = []
            barrier = threading.Barrier(250)

            def try_reserve_batch():
                barrier.wait()
                ok = event_model.reserve_tickets(event_id, TYPE_ID, 5)
                results.append(ok)

            threads = [threading.Thread(target=try_reserve_batch) for _ in range(250)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            successes = sum(1 for r in results if r)
            event = mock_db.events.find_one({"event_id": event_id})

            assert successes == 200
            assert event["ticket_types"][0]["tickets_reserved"] == 1000

    def test_mixed_reserve_confirm_release(self, app, mock_db):
        """Simular flujo completo: reservar, confirmar algunas, liberar otras."""
        with app.app_context():
            from app.models import event as event_model
            event_id = _create_test_event(mock_db, max_tickets=100)

            # 20 compradores reservan 5 entradas cada uno = 100 reservadas
            for _ in range(20):
                assert event_model.reserve_tickets(event_id, TYPE_ID, 5) is True

            # Ya no caben mas
            assert event_model.reserve_tickets(event_id, TYPE_ID, 1) is False

            # 15 pagan (confirmar), 5 cancelan (liberar)
            for _ in range(15):
                event_model.confirm_reservation(event_id, TYPE_ID, 5)
            for _ in range(5):
                event_model.release_reservation(event_id, TYPE_ID, 5)

            event = mock_db.events.find_one({"event_id": event_id})
            assert event["ticket_types"][0]["tickets_sold"] == 75
            assert event["ticket_types"][0]["tickets_reserved"] == 0

            # Las 25 liberadas estan disponibles
            assert event_model.reserve_tickets(event_id, TYPE_ID, 25) is True
