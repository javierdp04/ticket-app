"""Tests for the access codes system."""
import json
from unittest.mock import patch, MagicMock
from tests.conftest import CSRF_TOKEN

from app.models.event import (
    create_event,
    get_event,
    validate_and_consume_access_codes,
    release_access_codes,
)

CT = {"_csrf_token": CSRF_TOKEN}


# ---- Helpers ----

def _make_event_with_codes(reusable=False, codes=None):
    """Create an event with a ticket type that has access codes."""
    if codes is None:
        codes = [{"code": "VERANO2026", "used": False}, {"code": "AMIGO123", "used": False}]
    return create_event({
        "name": "Evento Codigos",
        "date": "2026-08-01T20:00",
        "venue": "Sala Test",
        "currency": "eur",
        "ticket_types": [{
            "name": "VIP",
            "price": 60.00,
            "max_tickets": 50,
            "access_codes_enabled": True,
            "access_codes_reusable": reusable,
            "access_codes": codes,
        }],
    })


def _make_event_without_codes():
    """Create an event with a ticket type that has no access codes."""
    return create_event({
        "name": "Evento Normal",
        "date": "2026-08-01T20:00",
        "venue": "Sala Test",
        "currency": "eur",
        "ticket_types": [{
            "name": "General",
            "price": 25.00,
            "max_tickets": 100,
        }],
    })


# ---- Model tests ----

class TestReusableCode:
    def test_codigo_correcto_devuelve_lista(self, mock_db):
        event = _make_event_with_codes(reusable=True, codes=[{"code": "FIESTA", "used": False}])
        tt = event["ticket_types"][0]
        result = validate_and_consume_access_codes(
            event["event_id"], tt["type_id"], "FIESTA",
        )
        assert result == ["FIESTA"]

    def test_codigo_case_insensitive(self, mock_db):
        event = _make_event_with_codes(reusable=True, codes=[{"code": "FIESTA", "used": False}])
        tt = event["ticket_types"][0]
        result = validate_and_consume_access_codes(
            event["event_id"], tt["type_id"], "fiesta",
        )
        assert result == ["FIESTA"]

    def test_codigo_incorrecto_devuelve_none(self, mock_db):
        event = _make_event_with_codes(reusable=True, codes=[{"code": "FIESTA", "used": False}])
        tt = event["ticket_types"][0]
        result = validate_and_consume_access_codes(
            event["event_id"], tt["type_id"], "WRONG",
        )
        assert result is None

    def test_codigo_reutilizable_no_cambia_estado(self, mock_db):
        event = _make_event_with_codes(reusable=True, codes=[{"code": "FIESTA", "used": False}])
        tt = event["ticket_types"][0]
        # Use it multiple times
        for _ in range(5):
            result = validate_and_consume_access_codes(
                event["event_id"], tt["type_id"], "FIESTA",
            )
            assert result == ["FIESTA"]
        # Code still unused in DB
        updated = get_event(event["event_id"])
        codes = updated["ticket_types"][0]["access_codes"]
        assert codes[0]["used"] is False


class TestSingleUseCode:
    def test_codigo_valido_se_consume(self, mock_db):
        event = _make_event_with_codes(reusable=False)
        tt = event["ticket_types"][0]
        result = validate_and_consume_access_codes(
            event["event_id"], tt["type_id"], ["VERANO2026"],
        )
        assert result == ["VERANO2026"]
        # Verify code is marked used in DB
        updated = get_event(event["event_id"])
        codes = {c["code"]: c["used"] for c in updated["ticket_types"][0]["access_codes"]}
        assert codes["VERANO2026"] is True
        assert codes["AMIGO123"] is False

    def test_cantidad_multiple_consume_varios(self, mock_db):
        event = _make_event_with_codes(reusable=False)
        tt = event["ticket_types"][0]
        result = validate_and_consume_access_codes(
            event["event_id"], tt["type_id"], ["VERANO2026", "AMIGO123"],
        )
        assert result is not None
        assert len(result) == 2
        assert "VERANO2026" in result
        assert "AMIGO123" in result
        # Both codes marked used
        updated = get_event(event["event_id"])
        codes = updated["ticket_types"][0]["access_codes"]
        assert all(c["used"] for c in codes)

    def test_codigo_incorrecto_devuelve_none(self, mock_db):
        event = _make_event_with_codes(reusable=False)
        tt = event["ticket_types"][0]
        result = validate_and_consume_access_codes(
            event["event_id"], tt["type_id"], ["WRONG"],
        )
        assert result is None

    def test_codigo_ya_usado_devuelve_none(self, mock_db):
        event = _make_event_with_codes(
            reusable=False,
            codes=[{"code": "USED1", "used": True}, {"code": "AVAIL", "used": False}],
        )
        tt = event["ticket_types"][0]
        result = validate_and_consume_access_codes(
            event["event_id"], tt["type_id"], ["USED1"],
        )
        assert result is None

    def test_codigo_duplicado_en_input_devuelve_none(self, mock_db):
        event = _make_event_with_codes(reusable=False)
        tt = event["ticket_types"][0]
        result = validate_and_consume_access_codes(
            event["event_id"], tt["type_id"], ["VERANO2026", "VERANO2026"],
        )
        assert result is None

    def test_case_insensitive_y_trim(self, mock_db):
        event = _make_event_with_codes(reusable=False)
        tt = event["ticket_types"][0]
        result = validate_and_consume_access_codes(
            event["event_id"], tt["type_id"], ["  verano2026  "],
        )
        assert result == ["VERANO2026"]

    def test_string_input_se_convierte_a_lista(self, mock_db):
        """A single string is accepted for backward compatibility."""
        event = _make_event_with_codes(reusable=False)
        tt = event["ticket_types"][0]
        result = validate_and_consume_access_codes(
            event["event_id"], tt["type_id"], "VERANO2026",
        )
        assert result == ["VERANO2026"]


class TestReleaseAccessCodes:
    def test_libera_codigos_consumidos(self, mock_db):
        event = _make_event_with_codes(reusable=False)
        tt = event["ticket_types"][0]
        # Consume
        consumed = validate_and_consume_access_codes(
            event["event_id"], tt["type_id"], ["VERANO2026", "AMIGO123"],
        )
        assert consumed is not None
        # Verify both used
        updated = get_event(event["event_id"])
        assert all(c["used"] for c in updated["ticket_types"][0]["access_codes"])
        # Release
        release_access_codes(event["event_id"], tt["type_id"], consumed)
        # Verify both free again
        updated = get_event(event["event_id"])
        assert all(not c["used"] for c in updated["ticket_types"][0]["access_codes"])

    def test_liberar_lista_vacia_no_falla(self, mock_db):
        event = _make_event_with_codes(reusable=False)
        tt = event["ticket_types"][0]
        release_access_codes(event["event_id"], tt["type_id"], [])

    def test_liberar_evento_inexistente_no_falla(self, mock_db):
        release_access_codes("nonexistent-event-id", "abc12345", ["CODE1"])


# ---- Admin form parsing tests ----

class TestAdminFormParsing:
    def _admin_login(self, client):
        client.post("/admin/login", data={**CT, "password": "testpass"})

    def test_crear_evento_con_codigos(self, client, mock_db):
        self._admin_login(client)
        response = client.post("/admin/event/create", data={
            **CT,
            "name": "Evento Codigos",
            "description": "Test",
            "date": "2026-08-01T20:00",
            "venue": "Sala",
            "currency": "eur",
            "type_name[]": ["VIP"],
            "type_price[]": ["50.00"],
            "type_max_tickets[]": ["10"],
            "type_id[]": [""],
            "access_codes_enabled[]": ["1"],
            "access_codes_reusable[]": ["0"],
            "access_codes_list[]": ["CODE1\nCODE2\nCODE3"],
        })
        assert response.status_code == 302
        # Verify in DB
        from app.models.event import get_all_events
        events = get_all_events()
        evt = events[0]
        tt = evt["ticket_types"][0]
        assert tt["access_codes_enabled"] is True
        assert tt["access_codes_reusable"] is False
        assert len(tt["access_codes"]) == 3
        assert tt["access_codes"][0]["code"] == "CODE1"
        assert tt["access_codes"][0]["used"] is False

    def test_crear_evento_con_codigo_reutilizable(self, client, mock_db):
        self._admin_login(client)
        response = client.post("/admin/event/create", data={
            **CT,
            "name": "Evento Reusable",
            "description": "",
            "date": "2026-08-01T20:00",
            "venue": "Sala",
            "currency": "eur",
            "type_name[]": ["VIP"],
            "type_price[]": ["50.00"],
            "type_max_tickets[]": ["10"],
            "type_id[]": [""],
            "access_codes_enabled[]": ["1"],
            "access_codes_reusable[]": ["1"],
            "access_codes_list[]": ["SUPERCODE"],
        })
        assert response.status_code == 302
        from app.models.event import get_all_events
        events = get_all_events()
        evt = events[0]
        tt = evt["ticket_types"][0]
        assert tt["access_codes_reusable"] is True
        assert len(tt["access_codes"]) == 1
        assert tt["access_codes"][0]["code"] == "SUPERCODE"

    def test_editar_evento_preserva_codigos_usados(self, client, mock_db):
        self._admin_login(client)
        # Create event with codes, some used
        event = _make_event_with_codes(
            reusable=False,
            codes=[
                {"code": "USED1", "used": True},
                {"code": "AVAIL1", "used": False},
            ],
        )
        tt = event["ticket_types"][0]
        # Update: replace available codes but keep used ones
        response = client.post(
            f"/admin/event/{event['event_id']}/update",
            data={
                **CT,
                "name": "Updated",
                "description": "",
                "date": "2026-08-01T20:00",
                "venue": "Sala",
                "currency": "eur",
                "type_name[]": [tt["name"]],
                "type_price[]": [str(tt["price"])],
                "type_max_tickets[]": [str(tt["max_tickets"])],
                "type_id[]": [tt["type_id"]],
                "access_codes_enabled[]": ["1"],
                "access_codes_reusable[]": ["0"],
                "access_codes_list[]": ["NEWCODE1\nNEWCODE2"],
            },
        )
        assert response.status_code == 302
        updated = get_event(event["event_id"])
        codes = updated["ticket_types"][0]["access_codes"]
        code_map = {c["code"]: c["used"] for c in codes}
        # Used code preserved
        assert code_map["USED1"] is True
        # Old unused code replaced by new ones
        assert "AVAIL1" not in code_map
        assert code_map["NEWCODE1"] is False
        assert code_map["NEWCODE2"] is False

    def test_codigos_normalizados_mayusculas_sin_duplicados(self, client, mock_db):
        self._admin_login(client)
        response = client.post("/admin/event/create", data={
            **CT,
            "name": "Norm Test",
            "description": "",
            "date": "2026-08-01T20:00",
            "venue": "Sala",
            "currency": "eur",
            "type_name[]": ["VIP"],
            "type_price[]": ["50.00"],
            "type_max_tickets[]": ["10"],
            "type_id[]": [""],
            "access_codes_enabled[]": ["1"],
            "access_codes_reusable[]": ["0"],
            "access_codes_list[]": ["abc\nABC\ndef"],
        })
        assert response.status_code == 302
        from app.models.event import get_all_events
        events = get_all_events()
        codes = events[0]["ticket_types"][0]["access_codes"]
        code_values = [c["code"] for c in codes]
        # All uppercase
        assert all(c == c.upper() for c in code_values)
        # No duplicates
        assert len(code_values) == len(set(code_values))
        assert "ABC" in code_values
        assert "DEF" in code_values


# ---- Checkout integration tests ----

class TestCheckoutWithReusableCode:
    @patch("app.routes.checkout.stripe_service.create_checkout_session")
    def test_codigo_valido_redirige_a_stripe(self, mock_stripe, client, mock_db):
        mock_session = MagicMock()
        mock_session.url = "https://checkout.stripe.com/test"
        mock_session.id = "cs_test_ac"
        mock_stripe.return_value = mock_session

        event = _make_event_with_codes(reusable=True, codes=[{"code": "VIP2026", "used": False}])
        tt = event["ticket_types"][0]
        response = client.post("/checkout/create-session", data={
            **CT,
            "event_id": event["event_id"],
            "buyer_first_name": "Ana",
            "buyer_last_name": "Garcia",
            "buyer_email": "ana@test.com",
            f"quantity_{tt['type_id']}": "1",
            f"access_code_{tt['type_id']}": "VIP2026",
            "attendee_first_name_1": "Ana",
            "attendee_last_name_1": "Garcia",
        })
        assert response.status_code == 303
        mock_stripe.assert_called_once()

    @patch("app.routes.checkout.stripe_service.create_checkout_session")
    def test_codigo_incorrecto_devuelve_400(self, mock_stripe, client, mock_db):
        event = _make_event_with_codes(reusable=True, codes=[{"code": "VIP2026", "used": False}])
        tt = event["ticket_types"][0]
        response = client.post("/checkout/create-session", data={
            **CT,
            "event_id": event["event_id"],
            "buyer_first_name": "Ana",
            "buyer_last_name": "Garcia",
            "buyer_email": "ana@test.com",
            f"quantity_{tt['type_id']}": "1",
            f"access_code_{tt['type_id']}": "WRONG",
            "attendee_first_name_1": "Ana",
            "attendee_last_name_1": "Garcia",
        })
        assert response.status_code == 400
        mock_stripe.assert_not_called()

    @patch("app.routes.checkout.stripe_service.create_checkout_session")
    def test_sin_codigo_cuando_requerido_devuelve_400(self, mock_stripe, client, mock_db):
        event = _make_event_with_codes(reusable=True, codes=[{"code": "VIP2026", "used": False}])
        tt = event["ticket_types"][0]
        response = client.post("/checkout/create-session", data={
            **CT,
            "event_id": event["event_id"],
            "buyer_first_name": "Ana",
            "buyer_last_name": "Garcia",
            "buyer_email": "ana@test.com",
            f"quantity_{tt['type_id']}": "1",
            "attendee_first_name_1": "Ana",
            "attendee_last_name_1": "Garcia",
        })
        assert response.status_code == 400
        mock_stripe.assert_not_called()

    @patch("app.routes.checkout.stripe_service.create_checkout_session")
    def test_ajax_codigo_incorrecto_devuelve_json(self, mock_stripe, client, mock_db):
        event = _make_event_with_codes(reusable=True, codes=[{"code": "VIP2026", "used": False}])
        tt = event["ticket_types"][0]
        response = client.post("/checkout/create-session",
            data={
                **CT,
                "event_id": event["event_id"],
                "buyer_first_name": "Ana",
                "buyer_last_name": "Garcia",
                "buyer_email": "ana@test.com",
                f"quantity_{tt['type_id']}": "1",
                f"access_code_{tt['type_id']}": "WRONG",
                "attendee_first_name_1": "Ana",
                "attendee_last_name_1": "Garcia",
            },
            headers={"X-Requested-With": "XMLHttpRequest"},
        )
        assert response.status_code == 400
        data = response.get_json()
        assert "error" in data
        assert "no valido" in data["error"].lower() or "codigo" in data["error"].lower()

    @patch("app.routes.checkout.stripe_service.create_checkout_session")
    def test_ajax_exito_devuelve_redirect_json(self, mock_stripe, client, mock_db):
        mock_session = MagicMock()
        mock_session.url = "https://checkout.stripe.com/test"
        mock_session.id = "cs_test_ajax"
        mock_stripe.return_value = mock_session

        event = _make_event_with_codes(reusable=True, codes=[{"code": "VIP2026", "used": False}])
        tt = event["ticket_types"][0]
        response = client.post("/checkout/create-session",
            data={
                **CT,
                "event_id": event["event_id"],
                "buyer_first_name": "Ana",
                "buyer_last_name": "Garcia",
                "buyer_email": "ana@test.com",
                f"quantity_{tt['type_id']}": "1",
                f"access_code_{tt['type_id']}": "VIP2026",
                "attendee_first_name_1": "Ana",
                "attendee_last_name_1": "Garcia",
            },
            headers={"X-Requested-With": "XMLHttpRequest"},
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data["redirect"] == "https://checkout.stripe.com/test"


class TestCheckoutWithSingleUseCodes:
    @patch("app.routes.checkout.stripe_service.create_checkout_session")
    def test_codigos_por_asistente_validos(self, mock_stripe, client, mock_db):
        mock_session = MagicMock()
        mock_session.url = "https://checkout.stripe.com/test"
        mock_session.id = "cs_test_su"
        mock_stripe.return_value = mock_session

        event = _make_event_with_codes(reusable=False)
        tt = event["ticket_types"][0]
        # Two attendees, each with their own code
        response = client.post("/checkout/create-session", data={
            **CT,
            "event_id": event["event_id"],
            "buyer_first_name": "Ana",
            "buyer_last_name": "Garcia",
            "buyer_email": "ana@test.com",
            f"quantity_{tt['type_id']}": "2",
            f"access_code_{tt['type_id']}[]": ["VERANO2026", "AMIGO123"],
            "attendee_first_name_1": "Ana",
            "attendee_last_name_1": "Garcia",
            "attendee_first_name_2": "Luis",
            "attendee_last_name_2": "Perez",
        })
        assert response.status_code == 303
        mock_stripe.assert_called_once()
        # Verify codes were consumed
        updated = get_event(event["event_id"])
        codes = updated["ticket_types"][0]["access_codes"]
        assert all(c["used"] for c in codes)

    @patch("app.routes.checkout.stripe_service.create_checkout_session")
    def test_un_codigo_incorrecto_rechaza_todo(self, mock_stripe, client, mock_db):
        event = _make_event_with_codes(reusable=False)
        tt = event["ticket_types"][0]
        response = client.post("/checkout/create-session", data={
            **CT,
            "event_id": event["event_id"],
            "buyer_first_name": "Ana",
            "buyer_last_name": "Garcia",
            "buyer_email": "ana@test.com",
            f"quantity_{tt['type_id']}": "2",
            f"access_code_{tt['type_id']}[]": ["VERANO2026", "BADCODE"],
            "attendee_first_name_1": "Ana",
            "attendee_last_name_1": "Garcia",
            "attendee_first_name_2": "Luis",
            "attendee_last_name_2": "Perez",
        })
        assert response.status_code == 400
        mock_stripe.assert_not_called()
        # Verify NO codes were consumed (rollback)
        updated = get_event(event["event_id"])
        codes = updated["ticket_types"][0]["access_codes"]
        assert all(not c["used"] for c in codes)

    @patch("app.routes.checkout.stripe_service.create_checkout_session")
    def test_codigos_insuficientes_devuelve_400(self, mock_stripe, client, mock_db):
        event = _make_event_with_codes(reusable=False)
        tt = event["ticket_types"][0]
        # Requesting 2 tickets but only sending 1 code
        response = client.post("/checkout/create-session", data={
            **CT,
            "event_id": event["event_id"],
            "buyer_first_name": "Ana",
            "buyer_last_name": "Garcia",
            "buyer_email": "ana@test.com",
            f"quantity_{tt['type_id']}": "2",
            f"access_code_{tt['type_id']}[]": ["VERANO2026"],
            "attendee_first_name_1": "Ana",
            "attendee_last_name_1": "Garcia",
            "attendee_first_name_2": "Luis",
            "attendee_last_name_2": "Perez",
        })
        assert response.status_code == 400
        mock_stripe.assert_not_called()


class TestCheckoutWithoutAccessCodes:
    """Ensure ticket types without access codes work exactly as before."""

    @patch("app.routes.checkout.stripe_service.create_checkout_session")
    def test_tipo_sin_codigo_funciona_normal(self, mock_stripe, client, mock_db):
        mock_session = MagicMock()
        mock_session.url = "https://checkout.stripe.com/test"
        mock_session.id = "cs_test_normal"
        mock_stripe.return_value = mock_session

        event = _make_event_without_codes()
        tt = event["ticket_types"][0]
        response = client.post("/checkout/create-session", data={
            **CT,
            "event_id": event["event_id"],
            "buyer_first_name": "Juan",
            "buyer_last_name": "Perez",
            "buyer_email": "juan@test.com",
            f"quantity_{tt['type_id']}": "2",
            "attendee_first_name_1": "Juan",
            "attendee_last_name_1": "Perez",
            "attendee_first_name_2": "Maria",
            "attendee_last_name_2": "Lopez",
        })
        assert response.status_code == 303
        mock_stripe.assert_called_once()


# ---- Webhook release tests ----

class TestWebhookReleaseCodes:
    @patch("app.routes.checkout.stripe_service.verify_webhook")
    def test_expiry_libera_codigos(self, mock_verify, client, mock_db):
        event = _make_event_with_codes(reusable=False)
        tt = event["ticket_types"][0]
        # Consume codes
        consumed = validate_and_consume_access_codes(
            event["event_id"], tt["type_id"], ["VERANO2026"],
        )
        assert consumed is not None
        # Verify code is used
        updated = get_event(event["event_id"])
        code_map = {c["code"]: c["used"] for c in updated["ticket_types"][0]["access_codes"]}
        assert code_map["VERANO2026"] is True

        # Simulate expired webhook with access codes in metadata
        items_meta = json.dumps([{"t": tt["type_id"], "q": 1}])
        codes_meta = json.dumps([{"t": tt["type_id"], "c": consumed}])
        mock_verify.return_value = {
            "type": "checkout.session.expired",
            "data": {
                "object": {
                    "id": "cs_expired_test",
                    "metadata": {
                        "event_id": event["event_id"],
                        "items": items_meta,
                        "access_codes": codes_meta,
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

        # Verify code is released
        updated = get_event(event["event_id"])
        code_map = {c["code"]: c["used"] for c in updated["ticket_types"][0]["access_codes"]}
        assert code_map["VERANO2026"] is False


# ---- Metadata parsing tests ----

class TestParseAccessCodesMetadata:
    def test_parse_valido(self):
        from app.services.ticket_service import parse_access_codes_from_metadata
        metadata = {"access_codes": json.dumps([{"t": "abc12345", "c": ["CODE1", "CODE2"]}])}
        result = parse_access_codes_from_metadata(metadata)
        assert result == {"abc12345": ["CODE1", "CODE2"]}

    def test_parse_vacio(self):
        from app.services.ticket_service import parse_access_codes_from_metadata
        assert parse_access_codes_from_metadata({}) == {}
        assert parse_access_codes_from_metadata({"access_codes": ""}) == {}

    def test_parse_json_invalido(self):
        from app.services.ticket_service import parse_access_codes_from_metadata
        assert parse_access_codes_from_metadata({"access_codes": "not json"}) == {}
