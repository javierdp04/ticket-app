"""Tests de las rutas publicas: pagina principal, detalle de evento, success, cancel."""


class TestPaginaPrincipal:
    def test_index_devuelve_200(self, client):
        response = client.get("/")
        assert response.status_code == 200

    def test_index_muestra_eventos_activos(self, client, created_event):
        response = client.get("/")
        assert b"Evento Existente" in response.data

    def test_index_no_muestra_eventos_finalizados(self, client, created_event):
        from app.models.event import change_status
        change_status(created_event["event_id"], "finished")
        response = client.get("/")
        assert b"Evento Existente" not in response.data

    def test_index_sin_eventos_muestra_mensaje(self, client):
        response = client.get("/")
        assert b"No hay eventos disponibles" in response.data


class TestDetalleEvento:
    def test_detalle_evento_existente(self, client, created_event):
        response = client.get(f"/event/{created_event['event_id']}")
        assert response.status_code == 200
        assert b"Evento Existente" in response.data
        assert b"Sala Principal" in response.data

    def test_detalle_evento_muestra_disponibles(self, client, created_event):
        response = client.get(f"/event/{created_event['event_id']}")
        assert b"50" in response.data  # max_tickets - tickets_sold

    def test_detalle_evento_inexistente_404(self, client):
        response = client.get("/event/no-existe")
        assert response.status_code == 404

    def test_detalle_evento_finalizado_404(self, client, created_event):
        from app.models.event import change_status
        change_status(created_event["event_id"], "finished")
        response = client.get(f"/event/{created_event['event_id']}")
        assert response.status_code == 404

    def test_detalle_evento_pausado_accesible(self, client, created_event):
        from app.models.event import change_status
        change_status(created_event["event_id"], "paused")
        response = client.get(f"/event/{created_event['event_id']}")
        assert response.status_code == 200


class TestPaginasInformativas:
    def test_success_devuelve_200(self, client):
        response = client.get("/success")
        assert response.status_code == 200
        assert b"exito" in response.data

    def test_cancel_devuelve_200(self, client):
        response = client.get("/cancel")
        assert response.status_code == 200
        assert b"cancelado" in response.data
