import pytest
import mongomock

import app as app_module
from app import create_app


@pytest.fixture()
def mock_db():
    """Reemplaza la conexion real de MongoDB por mongomock."""
    client = mongomock.MongoClient()
    database = client["ticketapp_test"]
    original_db = app_module.db
    app_module.db = database
    # Tambien parchear en los modelos que importan db al inicio
    import app.models.event as event_mod
    import app.models.ticket as ticket_mod
    event_mod.db = database
    ticket_mod.db = database
    yield database
    # Limpiar
    client.close()
    app_module.db = original_db
    event_mod.db = original_db
    ticket_mod.db = original_db


@pytest.fixture()
def app(mock_db):
    """Crea la app Flask en modo testing."""
    application = create_app()
    application.config.update({
        "TESTING": True,
        "SECRET_KEY": "test-secret",
        "ADMIN_PASSWORD": "testpass",
        "BASE_URL": "http://localhost:5000",
        "STRIPE_PUBLIC_KEY": "pk_test_fake",
        "STRIPE_SECRET_KEY": "sk_test_fake",
        "STRIPE_WEBHOOK_SECRET": "whsec_test_fake",
        "MAIL_SUPPRESS_SEND": True,
    })
    yield application


@pytest.fixture()
def client(app):
    """Cliente HTTP de pruebas."""
    return app.test_client()


@pytest.fixture()
def sample_event_data():
    """Datos de ejemplo para crear un evento."""
    return {
        "name": "Concierto Test",
        "description": "Un concierto de prueba",
        "date": "2026-07-15T21:00",
        "venue": "Sala Test",
        "price": "15.00",
        "currency": "eur",
        "max_tickets": "100",
    }


@pytest.fixture()
def created_event(mock_db):
    """Evento ya insertado en la BD de prueba."""
    from app.models.event import create_event
    return create_event({
        "name": "Evento Existente",
        "description": "Descripcion del evento",
        "date": "2026-08-20T20:00",
        "venue": "Sala Principal",
        "price": 25.00,
        "currency": "eur",
        "max_tickets": 50,
    })


@pytest.fixture()
def created_ticket(mock_db, created_event):
    """Ticket ya insertado en la BD de prueba."""
    from app.models.ticket import create_ticket
    return create_ticket({
        "event_id": created_event["event_id"],
        "order_id": "order-test-001",
        "buyer_name": "Juan Test",
        "buyer_email": "juan@test.com",
        "price": created_event["price"],
        "currency": created_event["currency"],
        "stripe_session_id": "cs_test_123",
        "stripe_payment_intent": "pi_test_123",
    })
