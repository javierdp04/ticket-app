# Eventum Spain -- Documentacion del Proyecto

## Indice
1. [Descripcion General](#descripcion-general)
2. [Stack Tecnologico](#stack-tecnologico)
3. [Estructura del Proyecto](#estructura-del-proyecto)
4. [Modelos de Datos](#modelos-de-datos)
5. [Flujo Completo de Compra](#flujo-completo-de-compra)
6. [Modulos y Funcionalidades](#modulos-y-funcionalidades)
7. [Panel de Administracion](#panel-de-administracion)
8. [Validacion de QR](#validacion-de-qr)
9. [Seguridad y Proteccion](#seguridad-y-proteccion)
10. [Variables de Entorno](#variables-de-entorno)
11. [Tests](#tests)
12. [Decisiones Tomadas](#decisiones-tomadas)
13. [Limpieza de reservas expiradas](#limpieza-de-reservas-expiradas)
14. [Pendientes / Decisiones Abiertas](#pendientes--decisiones-abiertas)

---

## Descripcion General

Aplicacion web full-stack para la **venta de entradas de multiples eventos**. El administrador puede crear y gestionar eventos desde un panel de administracion, definiendo **multiples tipos de entrada** por evento (ej: General, VIP, Backstage), cada uno con su propio precio y aforo. Los usuarios pueden comprar entradas seleccionando el tipo y la cantidad deseada, pagando con tarjeta (Stripe), y recibir automaticamente un **correo electronico HTML con un PDF adjunto por cada entrada**, conteniendo los datos de la entrada, el tipo, y un **codigo QR unico**. En el evento, ese QR puede escanearse desde una interfaz web para validar la entrada, ver el tipo de entrada y el nombre del asistente, y marcarla como usada.

### Caracteristicas principales
- Soporte para **multiples eventos** gestionados desde el panel de administracion
- **Multiples tipos de entrada** por evento con precio y aforo independiente (ej: General, VIP)
- Compra de **una o varias entradas de diferentes tipos** en una sola transaccion
- **Nombres individuales por asistente** (cada entrada tiene nombre propio)
- Pago online seguro mediante Stripe
- **Reserva atomica de entradas** con proteccion contra sobreventa (optimistic locking)
- Generacion automatica de un PDF por cada entrada comprada, con QR unico y tipo de entrada
- Envio automatico de todos los PDFs por correo electronico (HTML + texto plano)
- Validacion de QR en tiempo real mostrando nombre del asistente y tipo de entrada
- Panel de administracion con gestion de eventos, tipos de entrada y metricas
- Rate limiting en endpoints sensibles (login, checkout, scanner)
- Sanitizacion de todos los inputs (HTML stripping, validacion de UUID, email, etc.)
- Creacion idempotente de tickets (previene duplicados por webhook + success)
- Escaner QR protegido con PIN independiente por evento
- Imagen/banner opcional por evento (subida desde el panel de admin, max 5 MB)
- **Codigos de acceso por tipo de entrada** (reutilizables o de un solo uso) para ventas restringidas/invitaciones

---

## Stack Tecnologico

| Capa | Tecnologia |
|---|---|
| Back-end | Python + Flask |
| Base de datos | MongoDB (PyMongo) |
| Pagos | Stripe (Checkout Sessions + Webhooks) |
| Generacion de PDF | ReportLab |
| Generacion de QR | qrcode (Python library) |
| Envio de correo | Flask-Mail / SMTP |
| Rate limiting | Flask-Limiter |
| Front-end | HTML + CSS + JavaScript (Vanilla) |
| Escaneo QR | html5-qrcode (libreria JS, accede a la camara del dispositivo) |

---

## Estructura del Proyecto

```
ticket-app/
|
|-- app/
|   |-- __init__.py                 # Factory de la app Flask (Mail, Limiter, MongoDB)
|   |-- config.py                   # Variables de configuracion
|   |
|   |-- routes/
|   |   |-- __init__.py
|   |   |-- main.py                 # Ruta principal (listado de eventos)
|   |   |-- events.py               # Pagina publica de detalle de evento + compra
|   |   |-- checkout.py             # Logica de Stripe (crear sesion, webhook, success/cancel)
|   |   |-- tickets.py              # Descarga individual de entradas en PDF
|   |   |-- scanner.py              # Validacion de QR en tiempo real
|   |   |-- admin.py                # Panel de administracion y gestion de eventos
|   |
|   |-- services/
|   |   |-- __init__.py
|   |   |-- stripe_service.py       # Integracion con Stripe (Checkout Sessions)
|   |   |-- email_service.py        # Envio de correos HTML con PDFs adjuntos
|   |   |-- pdf_service.py          # Generacion del PDF de la entrada
|   |   |-- qr_service.py           # Generacion del QR unico
|   |   |-- ticket_service.py       # Logica de negocio de las entradas
|   |   |-- event_service.py        # Logica de negocio de los eventos
|   |
|   |-- models/
|   |   |-- __init__.py
|   |   |-- event.py                # Modelo de evento (MongoDB)
|   |   |-- ticket.py               # Modelo de entrada (MongoDB)
|   |
|   |-- utils/
|   |   |-- __init__.py
|   |   |-- sanitize.py             # Sanitizacion de inputs (clean, valid_uuid, valid_email, etc.)
|   |
|   |-- templates/
|   |   |-- base.html               # Layout base
|   |   |-- index.html              # Pagina principal (listado de eventos con rango de precios)
|   |   |-- event_detail.html       # Detalle de evento + selector de tipos de entrada
|   |   |-- success.html            # Pagina tras compra exitosa
|   |   |-- cancel.html             # Pagina si se cancela el pago
|   |   |-- scanner.html            # Interfaz de escaneo QR
|   |   |-- admin/
|   |   |   |-- login.html          # Login del panel de admin
|   |   |   |-- dashboard.html      # Panel de administracion general
|   |   |   |-- event_form.html     # Formulario crear/editar evento con tipos de entrada
|   |   |   |-- event_detail.html   # Metricas detalladas + desglose por tipo
|   |   |-- email/
|   |       |-- ticket_email.html   # Plantilla HTML del correo de entradas
|   |
|   |-- static/
|       |-- css/
|       |   |-- main.css
|       |-- js/
|       |   |-- checkout.js         # Logica del formulario de compra (multiples tipos)
|       |   |-- scanner.js          # Logica del escaner QR (camara)
|       |   |-- admin.js            # Confirmaciones del panel de admin
|       |-- uploads/
|           |-- events/             # Imagenes/banners subidos por evento
|
|-- tests/                          # Suite de tests (pytest + mongomock)
|-- .env                            # Variables de entorno (NO subir a git)
|-- .gitignore
|-- requirements.txt
|-- run.py                          # Punto de entrada de la app
```

---

## Modelos de Datos

### Coleccion: `events` (MongoDB)

Cada documento representa un evento gestionado por el administrador.

```json
{
  "_id": "ObjectId generado por MongoDB",
  "event_id": "UUID unico (ej: e1a2b3c4-...)",
  "name": "Nombre del evento",
  "description": "Descripcion del evento (texto libre)",
  "date": "2026-06-15T21:00",
  "venue": "Lugar del evento",
  "currency": "eur",
  "ticket_types": [
    {
      "type_id": "hex8chars",
      "name": "General",
      "price": 25.00,
      "max_tickets": 200,
      "tickets_sold": 0,
      "tickets_reserved": 0
    },
    {
      "type_id": "hex8chars",
      "name": "VIP",
      "price": 60.00,
      "max_tickets": 50,
      "tickets_sold": 0,
      "tickets_reserved": 0,
      "access_codes_enabled": true,
      "access_codes_reusable": false,
      "access_codes": [
        { "code": "VERANO2026", "used": false },
        { "code": "AMIGO123", "used": true }
      ]
    }
  ],
  "status": "active | paused | finished",
  "image_filename": "uuid-hex.jpg | null",
  "scanner_pin": "PIN de 6 digitos para el personal de puerta",
  "created_at": "2026-01-01T12:00:00Z",
  "updated_at": "2026-01-01T12:00:00Z"
}
```

**Campos de `ticket_types`:**
- `type_id` -- Identificador unico del tipo (generado automaticamente, 8 caracteres hex)
- `name` -- Nombre del tipo de entrada (ej: "General", "VIP", "Backstage")
- `price` -- Precio de este tipo de entrada
- `max_tickets` -- Aforo maximo para este tipo
- `tickets_sold` -- Entradas vendidas (confirmadas) de este tipo
- `tickets_reserved` -- Entradas reservadas (en proceso de pago) de este tipo
- `access_codes_enabled` -- (opcional, bool) Si `true`, este tipo requiere un codigo de acceso para comprar
- `access_codes_reusable` -- (opcional, bool) Si `true`, un unico codigo sirve para todos los compradores. Si `false`, cada codigo es de un solo uso
- `access_codes` -- (opcional, array) Lista de objetos `{ "code": "ABC", "used": false }`. Los codigos se almacenan en mayusculas. Para tipos reutilizables el array tiene un solo elemento y `used` permanece siempre `false`

**Estados posibles de `status`:**
- `active` -- evento visible en la pagina principal con venta de entradas habilitada
- `paused` -- evento visible pero con venta deshabilitada temporalmente
- `finished` -- evento pasado o cerrado, no aparece en la pagina principal

### Coleccion: `tickets` (MongoDB)

Cada documento representa **una entrada individual** comprada.

```json
{
  "_id": "ObjectId generado por MongoDB",
  "ticket_id": "UUID unico (ej: a3f9c2d1-...)",
  "event_id": "UUID del evento al que pertenece",
  "order_id": "UUID compartido por todas las entradas de una misma compra",
  "buyer_name": "Nombre del comprador",
  "buyer_email": "correo@ejemplo.com",
  "attendee_name": "Nombre del asistente (puede ser distinto al comprador)",
  "ticket_type_id": "ID del tipo de entrada",
  "ticket_type_name": "General",
  "price": 25.00,
  "currency": "eur",
  "stripe_session_id": "cs_live_...",
  "stripe_payment_intent": "pi_...",
  "access_code_used": "VERANO2026",
  "status": "paid | used | cancelled",
  "qr_code": "URL codificada en el QR",
  "created_at": "2026-01-01T20:00:00Z",
  "used_at": "2026-01-15T21:34:00Z | null"
}
```

**Estados posibles de `status`:**
- `paid` -- pago confirmado por Stripe, entrada valida
- `used` -- entrada ya escaneada y validada en el evento
- `cancelled` -- pago cancelado o reembolsado

**Nota sobre `order_id`:** Todas las entradas de una misma compra comparten el mismo `order_id`.

---

## Flujo Completo de Compra

```
Usuario entra en la pagina principal
        |
        v
Ve el listado de eventos activos (con rango de precios por tipo)
        |
        v
Selecciona un evento --> /event/<event_id>
        |
        v
Ve los tipos de entrada disponibles con precios y aforo
        |
        v
Selecciona cantidad por cada tipo + nombre de cada asistente
(+ codigo de acceso si el tipo lo requiere)
        |
        v
Si algun tipo requiere codigo de acceso:
  - Reutilizable: se valida que el codigo coincida
  - Un solo uso: se valida y consume cada codigo (uno por asistente)
  Si el codigo es incorrecto: error inline via AJAX sin cambiar de pagina
        |
        v
Flask reserva atomicamente las entradas solicitadas (optimistic locking)
Si falla alguna reserva, rollback de las anteriores + codigos consumidos
        |
        v
Flask crea una Stripe Checkout Session
(con line items por cada tipo de entrada seleccionado)
        |
        v
Usuario es redirigido a la pagina de pago de Stripe
        |
        |-- Pago cancelado --> /cancel
        |   Stripe envia webhook "session.expired"
        |   Se liberan las reservas + codigos de acceso consumidos
        |
        |-- Pago exitoso
                |
                v
        Stripe envia un Webhook a /checkout/webhook
                |
                v
        Flask verifica la firma del webhook
                |
                v
        Por cada entrada comprada:
            - Se genera un ticket_id (UUID unico)
            - Se asigna el nombre del asistente correspondiente
            - qr_service genera el QR
            - pdf_service genera el PDF con tipo de entrada
                |
                v
        Se confirman las reservas (reserved --> sold)
                |
                v
        email_service envia UN correo HTML con TODOS los PDFs adjuntos
                |
                v
        Usuario es redirigido a /success
```

> **Nota sobre idempotencia:** La creacion de tickets verifica `stripe_session_id` para evitar duplicados. Tanto el webhook como la pagina `/success` pueden intentar crear tickets, pero solo el primero en ejecutarse los crea realmente.

> **Nota sobre rendimiento:** La pagina `/success` lanza el procesamiento de tickets en un hilo en background y renderiza la pagina inmediatamente. El mecanismo principal de creacion de tickets es el webhook; `/success` actua como fallback idempotente.

### Sistema de reservas (tres fases)

1. **Reservar** (`reserve_tickets`): Incrementa `tickets_reserved` atomicamente usando optimistic locking. Verifica que `sold + reserved + quantity <= max_tickets`.
2. **Confirmar** (`confirm_reservation`): Tras pago exitoso, convierte reservas en ventas (`reserved -= qty`, `sold += qty`).
3. **Liberar** (`release_reservation`): Si el pago expira o se cancela, libera las reservas (`reserved -= qty`). Esto ocurre via webhook de Stripe (`session.expired`) o via el job de limpieza de reservas huerfanas.

---

## Modulos y Funcionalidades

### `routes/main.py`
- `GET /` -- Pagina principal con listado de eventos activos. Para cada evento muestra: nombre, fecha, lugar, rango de precios (o precio unico), y entradas disponibles totales.

### `routes/events.py`
- `GET /event/<event_id>` -- Detalle de evento con selector de tipos de entrada. Muestra cada tipo con nombre, precio, disponibilidad y campo de cantidad.

### `routes/checkout.py`
- `POST /checkout/create-session` -- Recibe event_id, nombre/apellidos del comprador, email, cantidades por tipo de entrada, nombres de asistentes, y codigos de acceso. Valida y consume codigos de acceso, reserva atomicamente las entradas, crea una Stripe Checkout Session con line items por tipo, y redirige a Stripe. Soporta peticiones AJAX (devuelve JSON con `redirect` o `error`). **Rate limited: 10/min.**
- `POST /checkout/webhook` -- Recibe eventos de Stripe. Procesa `checkout.session.completed` (crea tickets + confirma reservas) y `checkout.session.expired` (libera reservas + codigos de acceso consumidos).
- `GET /success` -- Pagina de confirmacion tras pago exitoso. Lanza en un hilo en background la creacion de tickets como fallback idempotente si el webhook no ha llegado aun (la pagina se renderiza inmediatamente).
- `GET /cancel` -- Pagina mostrada si el usuario cancela el pago.

### `routes/tickets.py`
- `GET /ticket/<ticket_id>` -- Descarga individual de una entrada en PDF.

### `routes/scanner.py`
- `GET /scanner/<event_id>` -- Interfaz web de escaneo QR para un evento. Requiere PIN.
- `POST /scanner/auth` -- Verifica el PIN del evento. **Rate limited: 10/min.**
- `POST /scanner/validate` -- Valida un ticket escaneado. Muestra nombre del asistente y tipo de entrada. **Rate limited: 30/min.**

### `routes/admin.py`
- `GET /admin` -- Panel principal con lista de eventos y metricas (vendidas/total, ingresos por tipo). **Protegido por contrasena.**
- `GET /admin/event/<event_id>` -- Metricas detalladas con desglose por tipo de entrada.
- `GET /admin/event/new` -- Formulario para crear evento con tipos de entrada dinamicos.
- `POST /admin/event/create` -- Procesa la creacion (con tipos de entrada).
- `GET /admin/event/<event_id>/edit` -- Formulario de edicion (preserva vendidas/reservadas).
- `POST /admin/event/<event_id>/update` -- Procesa la actualizacion.
- `POST /admin/event/<event_id>/status` -- Cambia estado (active/paused/finished). **Rate limited: 5/min en login.**

### `services/event_service.py`
- `create_event(data)` -- Crea evento con tipos de entrada. Genera event_id, type_ids y scanner_pin.
- `update_event(event_id, data)` -- Actualiza datos del evento (campos permitidos: name, description, date, venue, currency, ticket_types, image_filename).
- `save_image(file)` -- Valida (extension, content-type, max 5 MB) y guarda imagen.
- `delete_image(filename)` -- Elimina imagen del disco.
- `reserve_tickets(event_id, type_id, qty)` -- Reserva atomica con optimistic locking.
- `confirm_reservation(event_id, type_id, qty)` -- Confirma reserva (reserved -> sold).
- `release_reservation(event_id, type_id, qty)` -- Libera reserva.
- `validate_and_consume_access_codes(event_id, type_id, codes_input)` -- Valida y consume codigos de acceso atomicamente (optimistic locking). Para reutilizables recibe un string; para un solo uso, una lista de codigos individuales.
- `release_access_codes(event_id, type_id, codes)` -- Libera codigos de acceso consumidos (al expirar el pago).
- `get_total_capacity(event)` -- Suma `max_tickets` de todos los tipos.
- `get_total_sold(event)` -- Suma `tickets_sold` de todos los tipos.
- `get_total_available(event)` -- Suma `max_tickets - sold - reserved` de todos los tipos.

### `services/stripe_service.py`
- `create_checkout_session(event, buyer_name, buyer_email, items, attendee_names, consumed_codes)` -- Crea Stripe Checkout Session con line items por tipo. Almacena items, nombres de asistentes y codigos de acceso consumidos en metadata.
- `verify_webhook(payload, sig_header)` -- Verifica firma del webhook.

### `services/ticket_service.py`
- `create_tickets(stripe_session, event, items)` -- Crea N tickets (uno por entrada). Idempotente por `stripe_session_id`. Genera QR, PDF, y envia email. Asigna `access_code_used` a cada ticket si aplica.
- `parse_items_from_metadata(metadata)` -- Decodifica items compactos de metadata de Stripe.
- `parse_access_codes_from_metadata(metadata)` -- Decodifica codigos de acceso consumidos de metadata de Stripe.
- `validate_ticket(ticket_id)` -- Valida y marca como usada. Devuelve nombre del asistente y tipo de entrada.
- `get_event_stats(event_id)` -- Estadisticas agregadas (vendidas, usadas, ingresos).
- `get_recent_purchases(event_id, limit)` -- Ultimas compras de un evento.

### `services/pdf_service.py`
- `generate_pdf(ticket_data, event_data, qr_image)` -- PDF con nombre del evento, fecha, lugar, nombre del asistente, tipo de entrada, precio, ID de entrada y QR.

### `services/email_service.py`
- `send_ticket_email(buyer_email, buyer_name, event_data, pdf_list)` -- Correo con cuerpo HTML (usando plantilla `email/ticket_email.html`) + texto plano como fallback + PDFs adjuntos.

### `services/qr_service.py`
- `generate_qr(ticket_id)` -- QR que codifica la URL de validacion. Devuelve bytes de imagen PNG + URL.

### `utils/sanitize.py`
- `clean(value, max_length)` -- Limpia HTML tags, limita longitud.
- `valid_uuid(value)` -- Valida formato UUID.
- `valid_email(value)` -- Valida formato email.
- `valid_int(value, min, max, default)` -- Parsea entero con limites.
- `valid_float(value, min, default)` -- Parsea float con minimo.
- `valid_pin(value)` -- Valida PIN numerico (hasta 6 digitos).

---

## Panel de Administracion

Ruta: `GET /admin`
Acceso: protegido por contrasena definida en `.env` (`ADMIN_PASSWORD`)

### Vista principal (listado de eventos):
| Columna | Descripcion |
|---|---|
| Nombre del evento | Nombre + enlace al detalle |
| Fecha | Fecha del evento |
| Estado | active / paused / finished (con opcion de cambiar) |
| Vendidas / Total | Suma de tickets_sold / suma de max_tickets (todos los tipos) |
| Ingresos | Suma de (tickets_sold * precio) por cada tipo |
| Acciones | Editar, pausar/activar, finalizar |

### Formulario crear/editar evento:
- Nombre del evento (obligatorio)
- Descripcion (opcional)
- Fecha y hora (obligatorio)
- Lugar (obligatorio)
- Moneda (EUR, USD, GBP)
- **Tipos de entrada** (dinamicos, anadir/eliminar):
  - Nombre del tipo (ej: General, VIP)
  - Precio por entrada
  - Aforo maximo
  - **Codigo de acceso** (opcional): checkbox para activar, con opcion reutilizable (un unico codigo compartido) o de un solo uso (un codigo por asistente, introducidos en textarea). Al editar, los codigos ya utilizados se preservan automaticamente.
- Imagen/banner (opcional, JPG/PNG/WEBP, max 5 MB)

Al crear el evento, se genera automaticamente un `scanner_pin` de 6 digitos.

### Detalle de un evento (`/admin/event/<event_id>`):
| Metrica | Descripcion |
|---|---|
| Entradas vendidas | Total de tickets con status "paid" o "used" |
| Entradas restantes | Suma de (max_tickets - sold - reserved) por tipo |
| % de aforo ocupado | Barra de progreso visual |
| Ingresos totales | Calculados desde tickets reales en BD |
| Ya usadas / Sin usar | Desglose por estado |
| **Desglose por tipo** | Tabla con tipo, precio, vendidas, aforo y disponibles |
| PIN del escaner | Visible y copiable |
| Ultimas compras | Nombre del asistente, email, tipo de entrada, estado, fecha |

---

## Validacion de QR

### Funcionamiento:
1. El personal de puerta abre `/scanner/<event_id>` en su movil o tablet.
2. Se le pide el **PIN del evento** (6 digitos, proporcionado por el administrador).
3. Tras introducir el PIN correcto, se activa la camara usando **html5-qrcode**.
4. Al detectar un QR, `scanner.js` hace `POST /scanner/validate` con el `ticket_id`.
5. El servidor verifica que el ticket pertenece al evento correcto y responde con el estado.
6. La interfaz muestra:
   - **Verde**: entrada valida + nombre del asistente + tipo de entrada
   - **Rojo**: entrada ya usada o no valida (con motivo)

### Seguridad:
- PIN unico por evento, independiente de la contrasena de admin.
- El personal de puerta accede al escaner sin tener acceso al panel de administracion.
- Cada entrada solo puede pasar de `paid` a `used` una unica vez.
- Se verifica que el ticket pertenece al evento del escaner.

---

## Seguridad y Proteccion

### Sanitizacion de inputs
- Todos los inputs de formulario pasan por `utils/sanitize.py`
- HTML tags eliminados con regex
- UUIDs, emails, enteros y floats validados con funciones especificas
- Longitudes maximas aplicadas a todos los campos de texto

### Rate limiting (Flask-Limiter)
- Global: 120 peticiones/minuto por IP
- `/admin/login` POST: 5/minuto
- `/checkout/create-session`: 10/minuto
- `/scanner/auth`: 10/minuto
- `/scanner/validate`: 30/minuto

### Prevencion de sobreventa
- Optimistic locking en MongoDB para reservas atomicas
- Rollback automatico si falla la reserva de algun tipo de entrada
- Reservas liberadas automaticamente cuando Stripe envia evento `session.expired`
- Job de limpieza (`cleanup-reservations`) libera reservas huerfanas si el webhook falla (ver seccion Limpieza de reservas)

### Codigos de acceso
- Codigos normalizados a mayusculas y sanitizados con `utils/sanitize.py` (max 100 chars, sin HTML)
- Consumo atomico de codigos con optimistic locking (mismo patron que reservas)
- Codigos de un solo uso liberados automaticamente si el pago expira (almacenados en metadata de Stripe)
- Validacion via AJAX: errores mostrados inline sin recargar la pagina

### Idempotencia
- Creacion de tickets protegida por `stripe_session_id` (no se crean duplicados)

### Proteccion del panel de admin
- Contrasena configurada via variable de entorno
- Session-based authentication

---

## Variables de Entorno

Archivo `.env` (nunca subir a git):

```env
# Flask
FLASK_ENV=development
SECRET_KEY=clave_secreta_flask

# MongoDB
MONGO_URI=mongodb://localhost:27017/ticketapp

# Stripe
STRIPE_PUBLIC_KEY=pk_test_...
STRIPE_SECRET_KEY=sk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...

# Email (SMTP)
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=True
MAIL_USERNAME=tucorreo@gmail.com
MAIL_PASSWORD=contrasena_o_app_password

# Admin
ADMIN_PASSWORD=contrasena_panel_admin

# App
BASE_URL=https://localhost:5000
```

---

## Tests

Suite de 105 tests usando `pytest` y `mongomock`:

| Archivo | Cobertura |
|---|---|
| `test_concurrency.py` | Reservas atomicas, sobreventa, 1000 tickets con 250 hilos |
| `test_event_service.py` | CRUD de eventos, cambio de estado, PIN del scanner |
| `test_ticket_service.py` | Creacion de tickets, validacion, estadisticas |
| `test_routes_admin.py` | Login, CRUD de eventos, proteccion de rutas |
| `test_routes_checkout.py` | Checkout, webhook, validaciones |
| `test_routes_public.py` | Pagina principal, detalle de evento, success/cancel |
| `test_routes_scanner.py` | Autenticacion PIN, validacion de tickets |
| `test_image_upload.py` | Subida de imagenes, validacion de formato/tamano |
| `test_pdf_qr_service.py` | Generacion de PDFs y QRs |

Ejecutar: `source venv/bin/activate && python -m pytest tests/ -v`

---

## Decisiones Tomadas

| # | Decision | Resolucion |
|---|---|---|
| 1 | Evento unico vs multi-evento | **Multi-evento**: el admin crea eventos desde el panel |
| 2 | Entradas por compra | **Multiples tipos**: el usuario selecciona cantidad por cada tipo de entrada |
| 3 | Modelo de datos para tipos | **Array embebido** en el documento del evento (no coleccion separada) |
| 4 | Control de concurrencia | **Optimistic locking** con MongoDB positional operator `$` |
| 5 | Flujo de reservas | **Tres fases**: reserve -> confirm / release |
| 6 | Proteccion del escaner | **PIN separado por evento**, independiente de la contrasena de admin |
| 7 | Libreria de PDF | **ReportLab** (ligera, sin dependencias del sistema) |
| 8 | Email format | **HTML + texto plano** dual (con plantilla Jinja2 para HTML) |
| 9 | Idempotencia | **Verificacion por stripe_session_id** antes de crear tickets |
| 10 | Sanitizacion | **Modulo centralizado** (`utils/sanitize.py`) con funciones tipadas |
| 11 | Docker | No por ahora, se puede anadir mas adelante |

---

## Limpieza de reservas expiradas

Si un webhook de Stripe no llega (fallo de red, etc.), las reservas quedan huerfanas bloqueando entradas. El comando CLI `cleanup-reservations` libera estas reservas:

```bash
flask --app run cleanup-reservations --max-age 35
```

- `--max-age`: minutos de antiguedad minima para considerar una reserva expirada (por defecto 35, Stripe expira sesiones a los 30 min)
- Se recomienda ejecutar via cron cada 10 minutos:

```cron
*/10 * * * * cd /ruta/al/proyecto && /ruta/al/venv/bin/flask --app run cleanup-reservations --max-age 35
```

El proceso es atomico: cada reserva se elimina individualmente antes de liberar las entradas, evitando condiciones de carrera si multiples procesos ejecutan la limpieza simultaneamente.

---

## Pendientes / Decisiones Abiertas

| # | Decision | Estado |
|---|---|---|
| 1 | Proveedor de email (Gmail SMTP, SendGrid, Mailgun...) | Pendiente |
| 2 | Hosting y dominio | Pendiente |
| 3 | Certificado SSL para produccion (actualmente usa adhoc) | Pendiente |
| 4 | Diseno visual / branding (logo, colores) | Pendiente (funcional por ahora) |
| 5 | Migracion de eventos existentes sin ticket_types | Pendiente si hay datos legacy |

---

*Documentacion generada para uso interno del desarrollo. Actualizar conforme avance el proyecto.*
