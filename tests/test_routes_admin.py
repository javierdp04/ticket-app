"""Tests de las rutas de administracion."""


class TestAdminLogin:
    def test_login_page_devuelve_200(self, client):
        response = client.get("/admin/login")
        assert response.status_code == 200

    def test_login_correcto_redirige_a_dashboard(self, client):
        response = client.post("/admin/login", data={"password": "testpass"})
        assert response.status_code == 302
        assert "/admin" in response.headers["Location"]

    def test_login_incorrecto_muestra_error(self, client):
        response = client.post("/admin/login", data={"password": "wrong"})
        assert response.status_code == 200
        assert b"incorrecta" in response.data

    def test_dashboard_sin_login_redirige(self, client):
        response = client.get("/admin")
        assert response.status_code == 302
        assert "login" in response.headers["Location"]

    def test_logout_cierra_sesion(self, client):
        client.post("/admin/login", data={"password": "testpass"})
        client.get("/admin/logout")
        response = client.get("/admin")
        assert response.status_code == 302  # redirige a login


class TestAdminDashboard:
    def _login(self, client):
        client.post("/admin/login", data={"password": "testpass"})

    def test_dashboard_muestra_eventos(self, client, created_event):
        self._login(client)
        response = client.get("/admin")
        assert response.status_code == 200
        assert b"Evento Existente" in response.data

    def test_dashboard_sin_eventos(self, client):
        self._login(client)
        response = client.get("/admin")
        assert response.status_code == 200


class TestAdminCRUDEventos:
    def _login(self, client):
        client.post("/admin/login", data={"password": "testpass"})

    def test_formulario_nuevo_evento(self, client):
        self._login(client)
        response = client.get("/admin/event/new")
        assert response.status_code == 200
        assert b"Crear" in response.data

    def test_crear_evento(self, client, sample_event_data):
        self._login(client)
        response = client.post("/admin/event/create", data=sample_event_data)
        assert response.status_code == 302

        # Verificar que aparece en el dashboard
        response = client.get("/admin")
        assert b"Concierto Test" in response.data

    def test_editar_evento(self, client, created_event):
        self._login(client)
        response = client.get(f"/admin/event/{created_event['event_id']}/edit")
        assert response.status_code == 200
        assert b"Evento Existente" in response.data

    def test_actualizar_evento(self, client, created_event):
        self._login(client)
        response = client.post(
            f"/admin/event/{created_event['event_id']}/update",
            data={
                "name": "Nombre Actualizado",
                "description": "Nueva descripcion",
                "date": "2026-09-01T20:00",
                "venue": "Nuevo Lugar",
                "price": "35.00",
                "currency": "eur",
                "max_tickets": "200",
            },
        )
        assert response.status_code == 302

        response = client.get(f"/admin/event/{created_event['event_id']}")
        assert b"Nombre Actualizado" in response.data

    def test_cambiar_estado_evento(self, client, created_event):
        self._login(client)
        response = client.post(
            f"/admin/event/{created_event['event_id']}/status",
            data={"status": "paused"},
        )
        assert response.status_code == 302

        from app.services.event_service import get_event
        event = get_event(created_event["event_id"])
        assert event["status"] == "paused"

    def test_detalle_evento_admin(self, client, created_event):
        self._login(client)
        response = client.get(f"/admin/event/{created_event['event_id']}")
        assert response.status_code == 200
        assert b"Evento Existente" in response.data
        assert created_event["scanner_pin"].encode() in response.data

    def test_detalle_evento_inexistente(self, client):
        self._login(client)
        response = client.get("/admin/event/no-existe")
        assert response.status_code == 404
        assert b"no encontrado" in response.data


class TestAdminProteccion:
    def test_crear_evento_sin_login(self, client, sample_event_data):
        response = client.post("/admin/event/create", data=sample_event_data)
        assert response.status_code == 302
        assert "login" in response.headers["Location"]

    def test_editar_evento_sin_login(self, client, created_event):
        response = client.get(f"/admin/event/{created_event['event_id']}/edit")
        assert response.status_code == 302
        assert "login" in response.headers["Location"]

    def test_cambiar_estado_sin_login(self, client, created_event):
        response = client.post(
            f"/admin/event/{created_event['event_id']}/status",
            data={"status": "finished"},
        )
        assert response.status_code == 302
        assert "login" in response.headers["Location"]
