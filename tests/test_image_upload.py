import io
import os

import pytest

from app.services.event_service import UPLOAD_FOLDER, save_image, delete_image


@pytest.fixture(autouse=True)
def cleanup_uploads():
    """Limpia las imagenes subidas durante los tests."""
    yield
    if os.path.isdir(UPLOAD_FOLDER):
        for f in os.listdir(UPLOAD_FOLDER):
            os.remove(os.path.join(UPLOAD_FOLDER, f))


class FakeFile:
    """Simula un FileStorage de Werkzeug."""

    def __init__(self, filename, content_type, data=b"fake-image-data"):
        self.filename = filename
        self.content_type = content_type
        self._data = data
        self._pos = 0

    def seek(self, offset, whence=0):
        if whence == 2:
            self._pos = len(self._data)
        else:
            self._pos = offset

    def tell(self):
        return self._pos

    def save(self, path):
        with open(path, "wb") as f:
            f.write(self._data)

    def read(self, n=-1):
        return self._data


# -- Tests para save_image --

def test_save_image_jpg():
    f = FakeFile("photo.jpg", "image/jpeg")
    filename = save_image(f)
    assert filename is not None
    assert filename.endswith(".jpg")
    assert os.path.isfile(os.path.join(UPLOAD_FOLDER, filename))


def test_save_image_png():
    f = FakeFile("banner.png", "image/png")
    filename = save_image(f)
    assert filename.endswith(".png")


def test_save_image_webp():
    f = FakeFile("img.webp", "image/webp")
    filename = save_image(f)
    assert filename.endswith(".webp")


def test_save_image_returns_none_when_no_file():
    assert save_image(None) is None


def test_save_image_returns_none_when_empty_filename():
    f = FakeFile("", "image/jpeg")
    assert save_image(f) is None


def test_reject_invalid_extension():
    f = FakeFile("virus.exe", "image/jpeg")
    with pytest.raises(ValueError, match="Formato"):
        save_image(f)


def test_reject_gif_extension():
    f = FakeFile("anim.gif", "image/gif")
    with pytest.raises(ValueError, match="Formato"):
        save_image(f)


def test_reject_invalid_content_type():
    f = FakeFile("photo.jpg", "application/octet-stream")
    with pytest.raises(ValueError, match="contenido"):
        save_image(f)


def test_reject_too_large():
    big_data = b"x" * (6 * 1024 * 1024)  # 6 MB
    f = FakeFile("photo.jpg", "image/jpeg", data=big_data)
    with pytest.raises(ValueError, match="5 MB"):
        save_image(f)


def test_accept_exactly_5mb():
    data = b"x" * (5 * 1024 * 1024)
    f = FakeFile("photo.jpg", "image/jpeg", data=data)
    filename = save_image(f)
    assert filename is not None


# -- Tests para delete_image --

def test_delete_image_removes_file():
    f = FakeFile("photo.jpg", "image/jpeg")
    filename = save_image(f)
    path = os.path.join(UPLOAD_FOLDER, filename)
    assert os.path.isfile(path)
    delete_image(filename)
    assert not os.path.isfile(path)


def test_delete_image_none_does_not_raise():
    delete_image(None)


def test_delete_image_nonexistent_does_not_raise():
    delete_image("no-existe.jpg")


# -- Tests de integracion con rutas de admin --

from tests.conftest import CSRF_TOKEN
_CT = {"_csrf_token": CSRF_TOKEN}


def test_create_event_with_image(client, app):
    with client.session_transaction() as sess:
        sess["admin_authenticated"] = True

    data = {
        **_CT,
        "name": "Evento con imagen",
        "description": "Test",
        "date": "2026-09-01T20:00",
        "venue": "Sala Test",
        "currency": "eur",
        "type_name[]": ["General"],
        "type_price[]": ["10.00"],
        "type_max_tickets[]": ["50"],
        "type_id[]": [""],
        "image": (io.BytesIO(b"fake-image-data"), "banner.jpg"),
    }
    resp = client.post("/admin/event/create", data=data, content_type="multipart/form-data")
    assert resp.status_code == 302  # redirect al dashboard


def test_create_event_rejects_invalid_format(client, app):
    with client.session_transaction() as sess:
        sess["admin_authenticated"] = True

    data = {
        **_CT,
        "name": "Evento malo",
        "description": "",
        "date": "2026-09-01T20:00",
        "venue": "Sala",
        "currency": "eur",
        "type_name[]": ["General"],
        "type_price[]": ["10.00"],
        "type_max_tickets[]": ["50"],
        "type_id[]": [""],
        "image": (io.BytesIO(b"fake"), "virus.exe"),
    }
    resp = client.post("/admin/event/create", data=data, content_type="multipart/form-data")
    assert resp.status_code == 200  # se queda en el form con error
    assert b"Formato" in resp.data


def test_update_event_replaces_image(client, app, created_event):
    with client.session_transaction() as sess:
        sess["admin_authenticated"] = True

    # Primero subimos una imagen al evento
    f = FakeFile("old.jpg", "image/jpeg")
    old_filename = save_image(f)
    from app.services import event_service
    event_service.update_event(created_event["event_id"], {"image_filename": old_filename})
    old_path = os.path.join(UPLOAD_FOLDER, old_filename)
    assert os.path.isfile(old_path)

    # Ahora actualizamos con nueva imagen
    tt = created_event["ticket_types"][0]
    data = {
        **_CT,
        "name": created_event["name"],
        "description": created_event["description"],
        "date": created_event["date"],
        "venue": created_event["venue"],
        "currency": created_event["currency"],
        "type_name[]": [tt["name"]],
        "type_price[]": [str(tt["price"])],
        "type_max_tickets[]": [str(tt["max_tickets"])],
        "type_id[]": [tt["type_id"]],
        "image": (io.BytesIO(b"new-image-data"), "new.png"),
    }
    resp = client.post(
        f"/admin/event/{created_event['event_id']}/update",
        data=data,
        content_type="multipart/form-data",
    )
    assert resp.status_code == 302
    # La imagen anterior debe haberse eliminado
    assert not os.path.isfile(old_path)
