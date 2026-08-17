# Deploy en VPS con Nginx, systemd y Certbot

Esta guía prepara `asistenciamodelo.online` en un VPS Linux sin interferir con otras aplicaciones ya publicadas.

## Principios de aislamiento
- `nginx` usa **un server block exclusivo** por `server_name`: `asistenciamodelo.online`.
- El **backend** escucha solo en `127.0.0.1:8184`.
- El **frontend** escucha solo en `127.0.0.1:3101`.
- No se expone ningún puerto nuevo público además de `80/443`, que ya maneja `nginx`.
- `certbot` usa **webroot** en vez de reescribir automáticamente otros bloques `nginx`.
- El despliegue de producción **no** debe usar `docker compose`, `uvicorn --reload` ni `npm run dev`.
- Antes de desplegar, elimina cualquier binario o log ajeno al producto; el script bloquea artefactos sospechosos como `xmrig` o escáneres locales.

## Archivos preparados en el repo
- `infra/nginx/asistenciamodelo.online.http.conf`
- `infra/nginx/asistenciamodelo.online.conf`
- `infra/systemd/asistenciamodelo-backend.service`
- `infra/systemd/asistenciamodelo-frontend.service`
- `infra/env/backend.production.env.example`
- `infra/env/frontend.production.env.example`
- `infra/scripts/deploy_vps.sh`

## Requisitos en el VPS
```bash
sudo apt update
sudo apt install -y nginx certbot python3-certbot-nginx python3-venv build-essential python3-dev libpq-dev nodejs npm
```

## Layout recomendado
```text
/home/gaibarra/modeloasist
├── backend/
├── frontend/
├── infra/
└── docs/
```

También puedes usar otra ruta, pero el script toma por defecto **la carpeta real del repo donde vive**. Solo necesitas exportar `APP_ROOT` si quieres forzar otra ubicación.

## 1) Copiar el proyecto
```bash
cd /home/gaibarra
git clone <TU_REPO_URL> modeloasist
cd /home/gaibarra/modeloasist
```

## 2) Crear variables de entorno de producción
```bash
sudo mkdir -p /etc/asistenciamodelo
sudo cp infra/env/backend.production.env.example /etc/asistenciamodelo/backend.env
sudo cp infra/env/frontend.production.env.example /etc/asistenciamodelo/frontend.env
sudo nano /etc/asistenciamodelo/backend.env
sudo nano /etc/asistenciamodelo/frontend.env
```

### `/etc/asistenciamodelo/backend.env`
Valores importantes:
- `DATABASE_URL`: conexión real a PostgreSQL.
- `AUTH_SECRET_KEY`: un secreto largo y único.
- `AUTH_DEFAULT_PASSWORD`: contraseña temporal única, solo si realmente usarás `STARTUP_BOOTSTRAP_ENABLED=true`.
- `STARTUP_BOOTSTRAP_ENABLED=false`: recomendado en VPS para evitar sincronizaciones pesadas en cada arranque.
- `CORS_ALLOW_ORIGINS=https://asistenciamodelo.online`
- `ADMIN_EMAIL=gaibarra@hotmail.com`

### `/etc/asistenciamodelo/frontend.env`
Valores importantes:
- `API_BASE_URL=http://127.0.0.1:8184`
- `AUTH_SECRET_KEY`: debe ser exactamente el mismo valor configurado en `backend.env` para que Next.js pueda resolver la sesión SSR sin llamar a `/auth/me` en cada carga.
- `NEXT_PUBLIC_API_BASE_URL=https://asistenciamodelo.online`
- `NEXT_PUBLIC_CLIENT_API_BASE_URL=/api`

## 3) Instalar servicios y build de la app
```bash
cd /home/gaibarra/modeloasist
sudo bash infra/scripts/deploy_vps.sh
```

En esta primera ejecución, el script deja activo el bloque `HTTP` bootstrap para que `nginx -t` funcione sin depender todavía del certificado.

## 3.1) Verificar DNS antes de Certbot
`certbot` solo funcionará cuando **todos** los registros `A/AAAA` de `asistenciamodelo.online` apunten a este VPS.

Comprueba la resolución actual:
```bash
getent ahostsv4 asistenciamodelo.online
```

Debe salir únicamente `194.113.64.91`. Si aparece otra IP, como `2.57.91.91`, todavía hay un registro DNS viejo y Let's Encrypt puede validar contra el servidor equivocado.

Si ves múltiples IPs:
- elimina el `A`/`AAAA` sobrante en tu proveedor DNS,
- espera propagación,
- repite `getent ahostsv4 asistenciamodelo.online` hasta que solo quede la IP correcta.

Antes de lanzar `certbot`, valida además que el bloque bootstrap de `nginx` ya responde:
```bash
curl -I http://asistenciamodelo.online
curl -I http://127.0.0.1:3101/login
```

## 4) Emitir certificado TLS sin tocar otros vhosts
El bloque bootstrap ya deja activo `HTTP` con `webroot`. Emite el certificado así:
```bash
sudo certbot certonly \
  --webroot \
  -w /var/www/asistenciamodelo-certbot \
  -d asistenciamodelo.online \
  --email admin@asistenciamodelo.online \
  --agree-tos \
  --no-eff-email
```

Cuando el certificado exista, vuelve a ejecutar el deploy para activar el bloque HTTPS final:
```bash
cd /home/gaibarra/modeloasist
sudo bash infra/scripts/deploy_vps.sh
```

## 5) Habilitar inicio automático
```bash
sudo systemctl enable asistenciamodelo-backend.service
sudo systemctl enable asistenciamodelo-frontend.service
```

## 6) Verificación
```bash
systemctl status asistenciamodelo-backend.service --no-pager
systemctl status asistenciamodelo-frontend.service --no-pager
curl -I http://127.0.0.1:3101/login
curl -s http://127.0.0.1:8184/health/live
curl -I https://asistenciamodelo.online
```

## Renovación de certificados
`certbot` instala un timer de systemd. Puedes probar la renovación así:
```bash
sudo certbot renew --dry-run
```

## Logs útiles
```bash
journalctl -u asistenciamodelo-backend.service -n 200 --no-pager
journalctl -u asistenciamodelo-frontend.service -n 200 --no-pager
sudo tail -f /var/log/nginx/asistenciamodelo.error.log
```

## Endurecimiento recomendado
- Los servicios `systemd` ya incluyen límites de memoria/CPU y protecciones básicas; ajústalos según el plan real del VPS si observas reinicios por OOM.
- `nginx` aplica rate limiting general y uno más estricto para `POST /api/auth/login`.
- Verifica rotación de logs del sistema y monitorea `journalctl --disk-usage` para evitar crecimiento silencioso de disco.

## Notas para no interferir con otras apps del VPS
- No reemplaces `/etc/nginx/sites-enabled/default` si otras apps dependen de ese archivo.
- No uses `listen 80 default_server;` ni `listen 443 default_server;` en este proyecto.
- No expongas `3101` ni `8184` en firewall; deben quedar accesibles solo por `localhost`.
- Si otra app ya usa `certbot --nginx`, esta guía sigue siendo compatible porque el certificado se emite con `webroot` y el virtual host queda aislado por dominio.
