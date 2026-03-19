# Guia de despliegue — Eventum Spain

## 1. Requisitos previos

- **Servidor**: VPS con Ubuntu 22.04 (ej: Hetzner CX22 — 2 vCPU, 4GB RAM)
- **MongoDB Atlas**: cluster configurado (M0 gratuito suficiente para empezar)
- **Redis**: Redis Cloud free tier o Redis instalado en el servidor
- **Dominio**: con registro A apuntando a la IP del servidor
- **Email transaccional**: cuenta en Resend o Brevo (mejor entregabilidad que Gmail SMTP directo)

## 2. Preparacion del servidor

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3 python3-pip python3-venv nginx certbot python3-certbot-nginx git redis-server
```

Verificar que Redis esta activo:

```bash
sudo systemctl enable redis-server
sudo systemctl start redis-server
redis-cli ping
# Debe responder: PONG
```

## 3. Clonar y configurar la app

Crear usuario dedicado (opcional, no usar root):

```bash
sudo adduser eventum --disabled-password
sudo su - eventum
```

Clonar el repositorio:

```bash
git clone https://github.com/tu-usuario/ticket-app.git ~/ticket-app
cd ~/ticket-app
```

Crear entorno virtual e instalar dependencias:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Configurar variables de entorno:

```bash
cp .env.example .env
nano .env
```

Rellenar **todos** los valores en `.env`. Puntos criticos:

- `FLASK_ENV=production` (nunca `development` en el servidor)
- `SECRET_KEY=` generada con: `python3 -c "import secrets; print(secrets.token_hex(32))"`
- `BASE_URL=https://tudominio.com` (sin barra final, necesario para QRs y Stripe)
- `ADMIN_PASSWORD=` contrasena fuerte para el panel /admin

## 4. Configurar Nginx

Copiar la configuracion incluida en el repositorio:

```bash
sudo cp ~/ticket-app/nginx.conf /etc/nginx/sites-available/eventum
```

Editar el archivo — reemplazar `tudominio.com` y `tuusuario` por los valores reales:

```bash
sudo nano /etc/nginx/sites-available/eventum
```

Activar el sitio:

```bash
sudo ln -s /etc/nginx/sites-available/eventum /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
```

Verificar sintaxis y recargar:

```bash
sudo nginx -t
sudo systemctl reload nginx
```

Obtener certificado SSL con Certbot:

```bash
sudo certbot --nginx -d tudominio.com
```

Recargar Nginx para aplicar el certificado:

```bash
sudo systemctl reload nginx
```

## 5. Configurar Gunicorn como servicio systemd

Copiar el archivo de servicio:

```bash
sudo cp ~/ticket-app/eventum.service /etc/systemd/system/
```

Editar — reemplazar `tuusuario` y los paths por los valores reales:

```bash
sudo nano /etc/systemd/system/eventum.service
```

Activar y arrancar el servicio:

```bash
sudo systemctl daemon-reload
sudo systemctl enable eventum
sudo systemctl start eventum
```

Verificar que esta activo:

```bash
sudo systemctl status eventum
```

Debe mostrar `active (running)`.

## 6. Configurar Stripe webhook en produccion

1. Ir a **Stripe Dashboard > Developers > Webhooks > Add endpoint**
2. Endpoint URL: `https://tudominio.com/checkout/webhook`
3. Eventos a escuchar:
   - `checkout.session.completed`
   - `checkout.session.expired`
4. Copiar el **Signing secret** generado (empieza por `whsec_`)
5. Pegarlo en `.env` como `STRIPE_WEBHOOK_SECRET=whsec_...`
6. Reiniciar la app:

```bash
sudo systemctl restart eventum
```

## 7. Lista de verificacion final

- [ ] La web carga en https://tudominio.com sin errores
- [ ] El certificado SSL es valido (candado verde en el navegador)
- [ ] El panel /admin es accesible y el login funciona
- [ ] Se puede crear un evento desde el panel de administracion
- [ ] Las imagenes de eventos se suben y muestran correctamente
- [ ] El flujo completo de compra con Stripe en modo TEST funciona end-to-end
- [ ] Se recibe el email con el PDF adjunto al completar la compra
- [ ] El QR del PDF apunta a https:// (no http://) al abrirlo
- [ ] El escaner QR funciona desde el movil (requiere HTTPS para acceder a la camara)
- [ ] El webhook de Stripe aparece como exitoso en el Dashboard de Stripe
- [ ] Los tests pasan: `python -m pytest tests/ -v`

## 8. Actualizar la app tras cambios

La primera vez, dar permisos de ejecucion:

```bash
chmod +x deploy.sh
```

Para desplegar cambios:

```bash
bash deploy.sh
```

## 9. Comandos utiles de mantenimiento

```bash
# Ver logs en tiempo real
journalctl -u eventum -f

# Ver ultimas 100 lineas de logs
journalctl -u eventum -n 100

# Reiniciar la app
sudo systemctl restart eventum

# Estado del servicio
sudo systemctl status eventum

# Limpiar reservas huerfanas (Stripe expira sesiones a los 30 min)
cd ~/ticket-app && source venv/bin/activate
flask --app run cleanup-reservations --max-age 35

# Verificar renovacion SSL automatica
sudo certbot renew --dry-run

# Recargar Nginx sin downtime
sudo systemctl reload nginx
```
