# ticket-app -- Documentacion del Proyecto

## Indice
1. [Descripcion General](#descripcion-general)
2. [Stack Tecnologico](#stack-tecnologico)
3. [Estructura del Proyecto](#estructura-del-proyecto)
4. [Modelos de Datos](#modelos-de-datos)
5. [Flujo Completo de Compra](#flujo-completo-de-compra)
6. [Modulos y Funcionalidades](#modulos-y-funcionalidades)
7. [Panel de Administracion](#panel-de-administracion)
8. [Validacion de QR](#validacion-de-qr)
9. [Variables de Entorno](#variables-de-entorno)
10. [Decisiones Tomadas](#decisiones-tomadas)
11. [Pendientes / Decisiones Abiertas](#pendientes--decisiones-abiertas)

---

## Descripcion General

Aplicacion web full-stack para la **venta de entradas de multiples eventos**. El administrador puede crear y gestionar eventos desde un panel de administracion, y cada evento aparece en la pagina principal para que los usuarios puedan comprar entradas. El sistema permite a cualquier usuario comprar **una o varias entradas** de un evento pagando con tarjeta (Stripe), y recibir automaticamente un **correo electronico con un PDF adjunto por cada entrada**, conteniendo los datos de la entrada y un **codigo QR unico**. En el evento, ese QR puede escanearse desde una interfaz web para validar la entrada y marcarla como usada, evitando duplicados.

### Caracteristicas principales
- Soporte para **multiples eventos** gestionados desde el panel de administracion
- Compra de **una o varias entradas** en una sola transaccion (sin necesidad de registro, solo email)
- Pago online seguro mediante Stripe
- Generacion automatica de un PDF por cada entrada comprada, con QR unico
- Envio automatico de todos los PDFs por correo electronico
- Validacion de QR en tiempo real con marcado de entrada como "usada"
- Panel de administracion con gestion de eventos y metricas
- Aforo configurable por evento
- Precio configurable por evento
- Escaner QR protegido con PIN independiente por evento

---

## Stack Tecnologico

| Capa | Tecnologia |
|---|---|
| Back-end | Python + Flask |
| Base de datos | MongoDB |
| Pagos | Stripe (Checkout Sessions + Webhooks) |
| Generacion de PDF | ReportLab |
| Generacion de QR | qrcode (Python library) |
| Envio de correo | Flask-Mail / SMTP |
| Front-end | HTML + CSS + JavaScript (Vanilla) |
| Escaneo QR | html5-qrcode (libreria JS, accede a la camara del dispositivo) |
| Hosting | Pendiente de definir |

---

## Estructura del Proyecto

```
ticket-app/
|
|-- app/
|   |-- __init__.py                 # Factory de la app Flask
|   |-- config.py                   # Variables de configuracion
|   |
|   |-- routes/
|   |   |-- __init__.py
|   |   |-- main.py                 # Ruta principal (listado de eventos)
|   |   |-- checkout.py             # Logica de Stripe (crear sesion, webhook)
|   |   |-- tickets.py              # Generacion y descarga de entradas
|   |   |-- scanner.py              # Validacion de QR en tiempo real
|   |   |-- admin.py                # Panel de administracion y gestion de eventos
|   |   |-- events.py               # Pagina publica de detalle de evento + compra
|   |
|   |-- services/
|   |   |-- __init__.py
|   |   |-- stripe_service.py       # Integracion con Stripe
|   |   |-- email_service.py        # Envio de correos con PDFs adjuntos
|   |   |-- pdf_service.py          # Generacion del PDF de la entrada
|   |   |-- qr_service.py           # Generacion del QR unico
|   |   |-- ticket_service.py       # Logica de negocio de las entradas
|   |   |-- event_service.py        # Logica de negocio de los eventos
|   |
|   |-- models/
|   |   |-- __init__.py
|   |   |-- ticket.py               # Modelo de entrada (MongoDB)
|   |   |-- event.py                # Modelo de evento (MongoDB)
|   |
|   |-- templates/
|   |   |-- base.html               # Layout base
|   |   |-- index.html              # Pagina principal (listado de eventos)
|   |   |-- event_detail.html       # Detalle de evento + formulario de compra
|   |   |-- success.html            # Pagina tras compra exitosa
|   |   |-- cancel.html             # Pagina si se cancela el pago
|   |   |-- scanner.html            # Interfaz de escaneo QR
|   |   |-- admin/
|   |   |   |-- dashboard.html      # Panel de administracion general
|   |   |   |-- event_form.html     # Formulario crear/editar evento
|   |   |   |-- event_detail.html   # Metricas detalladas de un evento
|   |   |-- email/
|   |       |-- ticket_email.html   # Plantilla del correo
|   |
|   |-- static/
|       |-- css/
|       |   |-- main.css
|       |-- js/
|       |   |-- checkout.js         # Logica del formulario de compra
|       |   |-- scanner.js          # Logica del escaner QR (camara)
|       |   |-- admin.js            # Logica del panel de admin (formularios)
|       |-- img/
|           |-- logo.png
|
|-- .env                            # Variables de entorno (NO subir a git)
|-- .env.example                    # Plantilla de variables de entorno
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
  "date": "2026-06-15T21:00:00Z",
  "venue": "Lugar del evento",
  "price": 25.00,
  "currency": "eur",
  "max_tickets": 300,
  "tickets_sold": 0,
  "status": "active | paused | finished",
  "scanner_pin": "PIN de 6 digitos para el personal de puerta",
  "created_at": "2026-01-01T12:00:00Z",
  "updated_at": "2026-01-01T12:00:00Z"
}
```

**Estados posibles de `status`:**
- `active` -- evento visible en la pagina principal con venta de entradas habilitada
- `paused` -- evento visible pero con venta deshabilitada temporalmente (ej: sold out manual)
- `finished` -- evento pasado o cerrado, no aparece en la pagina principal

### Coleccion: `tickets` (MongoDB)

Cada documento representa **una entrada individual** comprada. Si un usuario compra 3 entradas, se generan 3 documentos.

```json
{
  "_id": "ObjectId generado por MongoDB",
  "ticket_id": "UUID unico (ej: a3f9c2d1-...)",
  "event_id": "UUID del evento al que pertenece",
  "order_id": "UUID compartido por todas las entradas de una misma compra",
  "buyer_name": "Nombre del comprador",
  "buyer_email": "correo@ejemplo.com",
  "price": 25.00,
  "currency": "eur",
  "stripe_session_id": "cs_live_...",
  "stripe_payment_intent": "pi_...",
  "status": "paid | used | cancelled",
  "qr_code": "URL codificada en el QR (apunta al endpoint de validacion)",
  "created_at": "2026-01-01T20:00:00Z",
  "used_at": "2026-01-15T21:34:00Z | null"
}
```

**Estados posibles de `status`:**
- `paid` -- pago confirmado por Stripe, entrada valida
- `used` -- entrada ya escaneada y validada en el evento
- `cancelled` -- pago cancelado o reembolsado

**Nota sobre `order_id`:** Todas las entradas generadas en una misma compra comparten el mismo `order_id`. Esto permite agrupar entradas por compra (ej: para reenviar todos los PDFs de una compra).

---

## Flujo Completo de Compra

```
Usuario entra en la pagina principal
        |
        v
Ve el listado de eventos activos
        |
        v
Selecciona un evento --> /event/<event_id>
        |
        v
Rellena formulario (nombre + email + cantidad de entradas)
        |
        v
Flask verifica que hay aforo suficiente
        |
        v
Flask crea una Stripe Checkout Session
(con quantity = numero de entradas solicitadas)
        |
        v
Usuario es redirigido a la pagina de pago de Stripe
        |
        |-- Pago cancelado --> /cancel (pagina de error / reintento)
        |
        |-- Pago exitoso
                |
                v
        Stripe envia un Webhook a /checkout/webhook
                |
                v
        Flask verifica la firma del webhook (seguridad)
                |
                v
        Por cada entrada comprada (segun quantity):
            - Se genera un ticket_id (UUID unico)
            - Se genera un order_id compartido (si es la primera)
            - qr_service genera el QR apuntando a:
              /scanner/validate/<ticket_id>
            - pdf_service genera el PDF con los datos + QR
                |
                v
        Todos los tickets se guardan en MongoDB con status="paid"
        Se incrementa tickets_sold en el evento
                |
                v
        email_service envia UN correo con TODOS los PDFs adjuntos
                |
                v
        Usuario es redirigido a /success
```

> **Importante:** La logica de creacion de tickets (generar QR, PDF, guardar en BD, enviar email) ocurre **dentro del webhook de Stripe**, NO en el redirect a `/success`. Esto garantiza que solo se generan entradas de pagos realmente confirmados.

---

## Modulos y Funcionalidades

### `routes/main.py`
- `GET /` -- Sirve la pagina principal con el listado de todos los eventos activos. Para cada evento muestra: nombre, fecha, lugar, precio, y entradas disponibles.

### `routes/events.py`
- `GET /event/<event_id>` -- Pagina publica de detalle de un evento con el formulario de compra (nombre, email, cantidad de entradas). Muestra toda la informacion del evento y el aforo restante.

### `routes/checkout.py`
- `POST /checkout/create-session` -- Recibe event_id, nombre, email y cantidad. Verifica aforo disponible, crea una Stripe Checkout Session con la cantidad correspondiente y redirige al usuario a Stripe.
- `POST /checkout/webhook` -- Endpoint que recibe eventos de Stripe. Solo procesa `checkout.session.completed`. Verifica la firma del webhook con la clave secreta de Stripe.
- `GET /success` -- Pagina de confirmacion tras pago exitoso (solo informativa, no ejecuta logica).
- `GET /cancel` -- Pagina mostrada si el usuario cancela el pago en Stripe.

### `routes/tickets.py`
- `GET /ticket/<ticket_id>` -- (Opcional) Permite al comprador descargar su entrada individual en PDF.
- `GET /tickets/order/<order_id>` -- (Opcional) Permite descargar todas las entradas de una compra.

### `routes/scanner.py`
- `GET /scanner/<event_id>` -- Sirve la interfaz web de escaneo para un evento concreto. Requiere introducir el PIN del evento para acceder.
- `POST /scanner/validate` -- Recibe el contenido del QR escaneado (ticket_id) y el event_id. Busca la entrada en MongoDB y:
  - Si `status == "paid"` y pertenece al evento correcto --> actualiza a `status = "used"`, guarda `used_at`, devuelve valida.
  - Si `status == "used"` --> devuelve ya usada (con la hora de primer uso).
  - Si no existe o no pertenece al evento --> devuelve no valida.
- `POST /scanner/auth` -- Verifica el PIN introducido para acceder al escaner de un evento.

### `routes/admin.py`
- `GET /admin` -- Panel principal. Muestra lista de todos los eventos con metricas resumidas. Acceso protegido por contrasena (`ADMIN_PASSWORD` en `.env`).
- `GET /admin/event/<event_id>` -- Metricas detalladas de un evento concreto.
- `GET /admin/event/new` -- Formulario para crear un nuevo evento.
- `POST /admin/event/create` -- Procesa la creacion de un nuevo evento.
- `GET /admin/event/<event_id>/edit` -- Formulario para editar un evento existente.
- `POST /admin/event/<event_id>/update` -- Procesa la actualizacion de un evento.
- `POST /admin/event/<event_id>/status` -- Cambia el estado de un evento (active/paused/finished).

### `services/event_service.py`
- `create_event(data)` -- Crea un nuevo evento en MongoDB con los datos proporcionados. Genera el event_id y el scanner_pin.
- `update_event(event_id, data)` -- Actualiza los datos de un evento.
- `change_status(event_id, new_status)` -- Cambia el estado de un evento.
- `get_event(event_id)` -- Recupera un evento por su ID.
- `get_active_events()` -- Devuelve todos los eventos con status "active" (para la pagina principal).
- `get_all_events()` -- Devuelve todos los eventos (para el panel de admin).
- `get_available_tickets(event_id)` -- Calcula las entradas disponibles: `max_tickets - tickets_sold`.
- `verify_scanner_pin(event_id, pin)` -- Verifica si el PIN proporcionado es correcto para un evento.

### `services/stripe_service.py`
- `create_checkout_session(event, buyer_name, buyer_email, quantity)` -- Crea y devuelve una Stripe Checkout Session con los datos del comprador, el precio del evento y la cantidad de entradas.
- `verify_webhook(payload, sig_header)` -- Verifica la firma del webhook de Stripe.

### `services/qr_service.py`
- `generate_qr(ticket_id)` -- Genera una imagen QR que codifica la URL de validacion: `https://<dominio>/scanner/validate/<ticket_id>`. Devuelve la imagen como bytes.

### `services/pdf_service.py`
- `generate_pdf(ticket_data, event_data, qr_image)` -- Genera un PDF con:
  - Nombre del evento, fecha y lugar
  - Nombre del comprador
  - Precio pagado
  - Codigo QR
  - Numero/ID de entrada
- Devuelve el PDF como bytes.

### `services/email_service.py`
- `send_ticket_email(buyer_email, buyer_name, event_data, pdf_list)` -- Envia un correo al comprador con:
  - Asunto: confirmacion de compra para el evento
  - Cuerpo HTML con los detalles del evento y la compra
  - Todos los PDFs adjuntos (uno por entrada comprada)

### `services/ticket_service.py`
- `create_tickets(stripe_session, event, quantity)` -- Orquesta la creacion de N entradas: genera ticket_ids, order_id, llama a qr_service y pdf_service por cada una, guarda en MongoDB, incrementa tickets_sold en el evento, y llama a email_service con todos los PDFs.
- `get_ticket(ticket_id)` -- Recupera un ticket de la BD por su ID.
- `get_tickets_by_order(order_id)` -- Recupera todos los tickets de una compra.
- `validate_ticket(ticket_id)` -- Valida y marca como usada una entrada. Devuelve el resultado.
- `get_event_stats(event_id)` -- Devuelve estadisticas agregadas de un evento para el panel de admin.

### `models/event.py`
- Define la estructura del documento de evento en MongoDB y los metodos de acceso a la base de datos (usando `pymongo` directamente).

### `models/ticket.py`
- Define la estructura del documento de ticket en MongoDB y los metodos de acceso a la base de datos (usando `pymongo` directamente).

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
| Vendidas / Total | Ej: "150 / 300" |
| Ingresos | Total recaudado para ese evento |
| Acciones | Editar, ver detalle, cambiar estado |

### Boton "Crear nuevo evento":
Formulario con los campos:
- Nombre del evento (obligatorio)
- Descripcion (opcional)
- Fecha y hora (obligatorio)
- Lugar (obligatorio)
- Precio por entrada (obligatorio)
- Moneda (por defecto EUR)
- Aforo maximo (obligatorio)

Al crear el evento, se genera automaticamente un `scanner_pin` de 6 digitos que el admin puede copiar y entregar al personal de puerta.

### Detalle de un evento (`/admin/event/<event_id>`):
| Metrica | Descripcion |
|---|---|
| Entradas vendidas | Total de tickets con `status = "paid"` o `"used"` |
| Entradas restantes | `max_tickets - tickets_sold` |
| % de aforo ocupado | Barra de progreso visual |
| Ingresos totales | `tickets_sold x precio` |
| Entradas ya usadas | Total de tickets con `status = "used"` |
| Entradas aun no usadas | Vendidas pero no presentadas todavia |
| PIN del escaner | PIN para el personal de puerta (visible, copiable) |
| Ultimas compras | Lista de las N compras mas recientes (nombre, email, cantidad, fecha) |

---

## Validacion de QR

El sistema de escaneo funciona integramente desde el navegador web, sin necesidad de app nativa.

### Funcionamiento:
1. El personal de puerta abre `/scanner/<event_id>` en su movil o tablet.
2. Se le pide el **PIN del evento** (6 digitos, proporcionado por el administrador).
3. Tras introducir el PIN correcto, se activa la camara del dispositivo usando la libreria **html5-qrcode** (JS).
4. Al detectar un QR, `scanner.js` hace una peticion `POST /scanner/validate` con el `ticket_id`.
5. El servidor verifica que el ticket pertenece al evento correcto y responde con el estado.
6. La interfaz muestra visualmente:
   - Verde: entrada valida (primera vez que se escanea) + nombre del comprador
   - Rojo: entrada ya usada (con la hora de primer uso) o no valida

### Seguridad:
- El acceso al escaner esta protegido por un **PIN unico por evento**, independiente de la contrasena de administrador.
- Esto permite que el personal de puerta acceda al escaner sin tener acceso al panel de administracion.
- Cada entrada solo puede pasar de `paid` a `used` una unica vez.
- El endpoint verifica que el ticket pertenece al evento del escaner para evitar validar entradas de otros eventos.

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
BASE_URL=http://localhost:5000
```

> **Nota:** Los datos de cada evento (nombre, fecha, lugar, precio, aforo) ya no se configuran en variables de entorno. Se gestionan dinamicamente desde el panel de administracion y se almacenan en MongoDB.

---

## Decisiones Tomadas

| # | Decision | Resolucion |
|---|---|---|
| 1 | Evento unico vs multi-evento | **Multi-evento**: el admin crea eventos desde el panel, se almacenan en MongoDB |
| 2 | Entradas por compra | **Multiples**: el usuario puede comprar N entradas en una sola transaccion |
| 3 | Diseno visual | **Funcional y minimalista** por ahora, se puede mejorar mas adelante |
| 4 | Proteccion del escaner | **PIN separado por evento**, independiente de la contrasena de admin |
| 5 | Libreria de PDF | **ReportLab** (ligera, sin dependencias del sistema) |
| 6 | Docker | **No por ahora**, se puede anadir mas adelante si es necesario |

---

## Pendientes / Decisiones Abiertas

| # | Decision | Estado |
|---|---|---|
| 1 | Proveedor de email (Gmail SMTP, SendGrid, Mailgun...) | Pendiente |
| 2 | Hosting y dominio | Pendiente |
| 3 | Diseno visual / branding (logo, colores) | Pendiente (funcional por ahora) |

---

*Documentacion generada para uso interno del desarrollo. Actualizar conforme avance el proyecto.*
