# Asistencia Frontend

Portal web en Next.js 16 para directivos y empleados. En local suele correr en `3001`; en VPS corre en `127.0.0.1:3101` detrás de `nginx`.

## Desarrollo local

El comando de desarrollo usa `.next-dev/` como caché independiente. Esto evita conflictos
con `.next/`, que puede pertenecer al proceso de despliegue en el mismo servidor.

```bash
cd frontend
export PORT=3001
export API_BASE_URL=http://127.0.0.1:8081
export NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8081
export NEXT_PUBLIC_CLIENT_API_BASE_URL=/api
npm install
npm run dev
```

Abre `http://127.0.0.1:3001`.

## Solución rápida para cache roto de `Next`

Si `npm run dev` llega a fallar con errores de `Turbopack` al escribir en `.next-dev`, limpia el cache local del frontend con:

```bash
cd frontend
npm run clean:dev-cache
```

Después vuelve a levantar el frontend con `npm run dev`.

## Variables relevantes
- `PORT`: puerto del servidor Next.js
- `API_BASE_URL`: URL interna que usa el servidor Next.js para llamar al backend
- `AUTH_SECRET_KEY`: en VPS debe coincidir con el secreto del backend para validar localmente el JWT de sesión en SSR
- `NEXT_PUBLIC_API_BASE_URL`: URL pública de respaldo para llamadas expuestas al cliente
- `NEXT_PUBLIC_CLIENT_API_BASE_URL`: base para las rutas proxy internas; en este proyecto normalmente `/api`

## Puertos por entorno
- `3001`: desarrollo local manual
- `3000`: flujo alterno con `docker-compose.yml`
- `3101`: despliegue VPS con `systemd`, solo accesible por `localhost`

## Producción VPS
- `systemd` arranca `npm run start -- --hostname 127.0.0.1 --port 3101`
- `nginx` publica el sitio en `https://asistenciamodelo.online`
- La guía operativa está en `docs/deploy-vps-nginx-systemd-certbot.md`
