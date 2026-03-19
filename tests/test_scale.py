"""Tests de escala: eventos con 3000+ asistentes, multiples tipos de entrada,
y muchos codigos de acceso por tipo."""
import json
import threading
import uuid
from unittest.mock import patch, MagicMock

import mongomock
import pytest
from tests.conftest import CSRF_TOKEN

CT = {"_csrf_token": CSRF_TOKEN}

from app.models.event import (
    create_event,
    get_event,
    reserve_tickets,
    confirm_reservation,
    release_reservation,
    validate_and_consume_access_codes,
    release_access_codes,
)


def _make_large_event(num_types=3, tickets_per_type=1000, codes_per_type=0, reusable=False):
    """Create an event with multiple ticket types, optionally with access codes."""
    ticket_types = []
    for i in range(num_types):
        tt = {
            "name": f"Tipo {i+1}",
            "price": 10.0 + i * 5,
            "max_tickets": tickets_per_type,
        }
        if codes_per_type > 0:
            tt["access_codes_enabled"] = True
            tt["access_codes_reusable"] = reusable
            if reusable:
                tt["access_codes"] = [{"code": f"REUSABLE{i}", "used": False}]
            else:
                tt["access_codes"] = [
                    {"code": f"T{i}C{j:04d}", "used": False}
                    for j in range(codes_per_type)
                ]
        ticket_types.append(tt)

    return create_event({
        "name": "Evento Grande 3000",
        "date": "2026-12-01T20:00",
        "venue": "Estadio Grande",
        "currency": "eur",
        "ticket_types": ticket_types,
    })


class TestLargeEventCreation:
    def test_crear_evento_3000_entradas_multiples_tipos(self, mock_db):
        """Create an event with 3 ticket types, 1000 each = 3000 capacity."""
        event = _make_large_event(num_types=3, tickets_per_type=1000)
        assert len(event["ticket_types"]) == 3
        total_capacity = sum(tt["max_tickets"] for tt in event["ticket_types"])
        assert total_capacity == 3000

        # Verify it can be retrieved
        retrieved = get_event(event["event_id"])
        assert retrieved is not None
        assert len(retrieved["ticket_types"]) == 3

    def test_crear_evento_5_tipos_diferentes(self, mock_db):
        """Create an event with 5 ticket types of different sizes."""
        event = create_event({
            "name": "Evento Multi-tipo",
            "date": "2026-12-01T20:00",
            "venue": "Gran Sala",
            "currency": "eur",
            "ticket_types": [
                {"name": "General", "price": 15.0, "max_tickets": 1500},
                {"name": "VIP", "price": 50.0, "max_tickets": 500},
                {"name": "Premium", "price": 100.0, "max_tickets": 200},
                {"name": "Backstage", "price": 200.0, "max_tickets": 50,
                 "access_codes_enabled": True, "access_codes_reusable": True,
                 "access_codes": [{"code": "BACKSTAGE", "used": False}]},
                {"name": "Prensa", "price": 0.0, "max_tickets": 100,
                 "access_codes_enabled": True, "access_codes_reusable": False,
                 "access_codes": [{"code": f"PRENSA{i:03d}", "used": False} for i in range(100)]},
            ],
        })
        total = sum(tt["max_tickets"] for tt in event["ticket_types"])
        assert total == 2350
        assert len(event["ticket_types"]) == 5


class TestLargeEventReservations:
    def test_reservar_3000_entradas_secuencialmente(self, mock_db):
        """Reserve 3000 tickets across 3 types, 1 at a time."""
        event = _make_large_event(num_types=3, tickets_per_type=1000)
        for tt in event["ticket_types"]:
            for _ in range(1000):
                assert reserve_tickets(event["event_id"], tt["type_id"], 1) is True
            # One more should fail
            assert reserve_tickets(event["event_id"], tt["type_id"], 1) is False

        retrieved = get_event(event["event_id"])
        for tt in retrieved["ticket_types"]:
            assert tt["tickets_reserved"] == 1000

    def test_reservar_lotes_grandes(self, mock_db):
        """Reserve in large batches (20 tickets at a time)."""
        event = _make_large_event(num_types=1, tickets_per_type=3000)
        tt = event["ticket_types"][0]
        for _ in range(150):
            assert reserve_tickets(event["event_id"], tt["type_id"], 20) is True
        # 150 * 20 = 3000, one more should fail
        assert reserve_tickets(event["event_id"], tt["type_id"], 1) is False

    def test_confirmar_y_liberar_3000(self, mock_db):
        """Reserve 3000, confirm half, release half, verify counts."""
        event = _make_large_event(num_types=1, tickets_per_type=3000)
        tt = event["ticket_types"][0]

        # Reserve all 3000
        assert reserve_tickets(event["event_id"], tt["type_id"], 3000) is True

        # Confirm 1500
        confirm_reservation(event["event_id"], tt["type_id"], 1500)

        # Release 1500
        release_reservation(event["event_id"], tt["type_id"], 1500)

        retrieved = get_event(event["event_id"])
        rtt = retrieved["ticket_types"][0]
        assert rtt["tickets_sold"] == 1500
        assert rtt["tickets_reserved"] == 0

        # Can reserve the 1500 freed spots
        assert reserve_tickets(event["event_id"], tt["type_id"], 1500) is True


class TestLargeAccessCodes:
    def test_3000_codigos_no_reutilizables(self, mock_db):
        """Create and validate 3000 single-use access codes."""
        event = _make_large_event(num_types=1, tickets_per_type=3000, codes_per_type=3000)
        tt = event["ticket_types"][0]
        assert len(tt["access_codes"]) == 3000

        # Consume first 20 codes
        codes_to_use = [f"T0C{i:04d}" for i in range(20)]
        result = validate_and_consume_access_codes(
            event["event_id"], tt["type_id"], codes_to_use
        )
        assert result is not None
        assert len(result) == 20

        # Verify they're marked used
        updated = get_event(event["event_id"])
        used_count = sum(1 for ac in updated["ticket_types"][0]["access_codes"] if ac["used"])
        assert used_count == 20

        # Try to reuse one — should fail
        result = validate_and_consume_access_codes(
            event["event_id"], tt["type_id"], ["T0C0000"]
        )
        assert result is None

    def test_consumir_y_liberar_muchos_codigos(self, mock_db):
        """Consume 100 codes, release them, consume again."""
        event = _make_large_event(num_types=1, tickets_per_type=3000, codes_per_type=3000)
        tt = event["ticket_types"][0]

        codes = [f"T0C{i:04d}" for i in range(100)]
        consumed = validate_and_consume_access_codes(
            event["event_id"], tt["type_id"], codes
        )
        assert consumed is not None

        # Release
        release_access_codes(event["event_id"], tt["type_id"], consumed)

        # Consume again
        consumed2 = validate_and_consume_access_codes(
            event["event_id"], tt["type_id"], codes
        )
        assert consumed2 is not None

    def test_codigo_reutilizable_multiples_reservas(self, mock_db):
        """Reusable code works for many reservations."""
        event = _make_large_event(num_types=1, tickets_per_type=3000, codes_per_type=1, reusable=True)
        tt = event["ticket_types"][0]

        # Use the code 100 times
        for _ in range(100):
            result = validate_and_consume_access_codes(
                event["event_id"], tt["type_id"], "REUSABLE0"
            )
            assert result == ["REUSABLE0"]


class TestLargeEventConcurrency:
    def test_3000_tickets_concurrent_reservations(self, mock_db):
        """300 threads each trying to reserve 10 tickets for a 3000-ticket event.
        Exactly 300 should succeed."""
        event = _make_large_event(num_types=1, tickets_per_type=3000)
        tt = event["ticket_types"][0]

        results = []
        num_threads = 300
        barrier = threading.Barrier(num_threads)

        def try_reserve():
            barrier.wait()
            ok = reserve_tickets(event["event_id"], tt["type_id"], 10)
            results.append(ok)

        threads = [threading.Thread(target=try_reserve) for _ in range(num_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        successes = sum(1 for r in results if r)
        retrieved = get_event(event["event_id"])
        reserved = retrieved["ticket_types"][0]["tickets_reserved"]

        assert successes == 300
        assert reserved == 3000

    def test_concurrent_access_code_consumption(self, mock_db):
        """Multiple threads trying to consume the same codes concurrently.
        Only one should succeed per code."""
        num_codes = 50
        event = _make_large_event(num_types=1, tickets_per_type=3000, codes_per_type=num_codes)
        tt = event["ticket_types"][0]

        results = []
        barrier = threading.Barrier(10)

        def try_consume():
            barrier.wait()
            # Each thread tries to consume the first code
            ok = validate_and_consume_access_codes(
                event["event_id"], tt["type_id"], ["T0C0000"]
            )
            results.append(ok)

        threads = [threading.Thread(target=try_consume) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Exactly 1 should succeed (optimistic locking)
        successes = sum(1 for r in results if r is not None)
        assert successes == 1

    def test_multiple_types_concurrent(self, mock_db):
        """Concurrent reservations across different ticket types."""
        event = _make_large_event(num_types=3, tickets_per_type=1000)

        results = {tt["type_id"]: [] for tt in event["ticket_types"]}
        barrier = threading.Barrier(150)  # 50 per type

        def try_reserve(type_id):
            barrier.wait()
            ok = reserve_tickets(event["event_id"], type_id, 20)
            results[type_id].append(ok)

        threads = []
        for tt in event["ticket_types"]:
            for _ in range(50):
                t = threading.Thread(target=try_reserve, args=(tt["type_id"],))
                threads.append(t)

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        for tt in event["ticket_types"]:
            successes = sum(1 for r in results[tt["type_id"]] if r)
            assert successes == 50  # 50 * 20 = 1000


class TestCheckout3000Attendees:
    @patch("app.routes.checkout.stripe_service.create_checkout_session")
    def test_compra_20_entradas_multiples_tipos(self, mock_stripe, client, mock_db):
        """Buy max allowed (20) tickets across multiple types."""
        mock_session = MagicMock()
        mock_session.url = "https://checkout.stripe.com/large"
        mock_session.id = "cs_large_test"
        mock_stripe.return_value = mock_session

        event = _make_large_event(num_types=2, tickets_per_type=1500)
        tt1 = event["ticket_types"][0]
        tt2 = event["ticket_types"][1]

        form_data = {
            **CT,
            "event_id": event["event_id"],
            "buyer_first_name": "Comprador",
            "buyer_last_name": "Grande",
            "buyer_email": "grande@test.com",
            f"quantity_{tt1['type_id']}": "10",
            f"quantity_{tt2['type_id']}": "10",
        }
        # Add attendee names for all 20
        for i in range(1, 21):
            form_data[f"attendee_first_name_{i}"] = f"Asistente{i}"
            form_data[f"attendee_last_name_{i}"] = f"Apellido{i}"

        response = client.post("/checkout/create-session", data=form_data)
        assert response.status_code == 303
        mock_stripe.assert_called_once()

    @patch("app.routes.checkout.stripe_service.create_checkout_session")
    def test_compra_con_codigos_no_reutilizables_multiples(self, mock_stripe, client, mock_db):
        """Buy tickets with non-reusable codes across multiple types."""
        mock_session = MagicMock()
        mock_session.url = "https://checkout.stripe.com/codes"
        mock_session.id = "cs_codes_test"
        mock_stripe.return_value = mock_session

        event = create_event({
            "name": "Evento Codigos Grandes",
            "date": "2026-12-01T20:00",
            "venue": "Gran Sala",
            "currency": "eur",
            "ticket_types": [
                {
                    "name": "VIP",
                    "price": 50.0,
                    "max_tickets": 3000,
                    "access_codes_enabled": True,
                    "access_codes_reusable": False,
                    "access_codes": [{"code": f"VIP{i:04d}", "used": False} for i in range(3000)],
                },
                {
                    "name": "General",
                    "price": 15.0,
                    "max_tickets": 3000,
                },
            ],
        })
        tt_vip = event["ticket_types"][0]
        tt_gen = event["ticket_types"][1]

        form_data = {
            **CT,
            "event_id": event["event_id"],
            "buyer_first_name": "Ana",
            "buyer_last_name": "Garcia",
            "buyer_email": "ana@test.com",
            f"quantity_{tt_vip['type_id']}": "5",
            f"quantity_{tt_gen['type_id']}": "5",
            f"access_code_{tt_vip['type_id']}[]": [f"VIP{i:04d}" for i in range(5)],
        }
        for i in range(1, 11):
            form_data[f"attendee_first_name_{i}"] = f"Asistente{i}"
            form_data[f"attendee_last_name_{i}"] = f"Apellido{i}"

        response = client.post("/checkout/create-session", data=form_data)
        assert response.status_code == 303

        # Verify codes consumed
        updated = get_event(event["event_id"])
        vip_codes = updated["ticket_types"][0]["access_codes"]
        used_count = sum(1 for c in vip_codes if c["used"])
        assert used_count == 5


class TestStripeMetadataScale:
    def test_metadata_con_muchos_codigos_no_excede_limite(self, mock_db):
        """Stripe metadata has a 500-char limit per value. Verify compact format works."""
        from app.services.stripe_service import create_checkout_session
        from unittest.mock import patch as p

        event = create_event({
            "name": "Test Meta",
            "date": "2026-12-01T20:00",
            "venue": "Sala",
            "currency": "eur",
            "ticket_types": [
                {"name": "VIP", "price": 50.0, "max_tickets": 100},
            ],
        })

        # 20 codes with 8 chars each
        consumed_codes = {
            event["ticket_types"][0]["type_id"]: [f"CODE{i:04d}" for i in range(20)]
        }

        with p("stripe.checkout.Session.create") as mock_create, \
             p("stripe.api_key", "sk_test"):
            mock_create.return_value = MagicMock(url="https://test.com", id="cs_test")

            from flask import Flask
            app = Flask(__name__)
            app.config["STRIPE_SECRET_KEY"] = "sk_test"
            app.config["BASE_URL"] = "http://localhost:5000"

            with app.app_context():
                session = create_checkout_session(
                    event, "Buyer Name", "buyer@test.com",
                    [{"type_id": event["ticket_types"][0]["type_id"],
                      "type_name": "VIP", "quantity": 20, "price": 50.0}],
                    [f"Asistente {i}" for i in range(20)],
                    consumed_codes,
                )

            call_args = mock_create.call_args
            metadata = call_args[1]["metadata"] if "metadata" in call_args[1] else call_args[0][0]

            # All metadata values must be under 500 chars
            for key, val in metadata.items():
                assert len(str(val)) <= 500, f"metadata[{key}] exceeds 500 chars: {len(str(val))}"
