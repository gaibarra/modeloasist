# Plataforma de Analítica de Asistencia

Monorepo que contiene los componentes necesarios para analizar la asistencia de empleados,
aplicar insights con IA (Google Vertex AI) y exponer experiencias personalizadas para
colaboradores y directivos.

## Estructura
- `frontend/`: Next.js 16 + Tailwind para portales de empleados y líderes.
- `backend/`: FastAPI + SQLAlchemy + Vertex AI SDK para APIs, análisis y coaching inteligente.
- `shared/`: Espacio reservado para librerías compartidas (modelos, utilidades, contratos de API).
- `infra/`: Plantillas de despliegue (Docker, Kubernetes, GitHub Actions) y configuración operativa.
- `docs/`: Documentación funcional y técnica.

## Primeros pasos
1. **Backend local**
   ```bash
   cd backend
   python -m venv .venv && source .venv/bin/activate
   pip install .[dev]
   cp .env.example .env
   uvicorn app.main:app --reload --port 8081
   ```
2. **Frontend local**
   ```bash
   cd frontend
   export PORT=3001
   export API_BASE_URL=http://127.0.0.1:8081
   export NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8081
   export NEXT_PUBLIC_CLIENT_API_BASE_URL=/api
   npm install
   npm run dev
   ```
3. Configura las variables de entorno tomando como referencia `backend/.env.example` y tu
   conexión a PostgreSQL/Vertex AI. El archivo `.env` debe apuntar a la base `asistencia`, por
   ejemplo:
   ```bash
   APP_ENV=local
   API_PORT=8081
   DATABASE_URL="postgresql+psycopg://gaibarra:6Vlgpcr&@localhost:5432/asistencia"
   ```

## Puertos por entorno
- **Local manual**: backend en `127.0.0.1:8081` y frontend en `127.0.0.1:3001`.
- **Docker Compose**: backend en `127.0.0.1:8080`, frontend en `127.0.0.1:3000` y PostgreSQL en `127.0.0.1:5432`.
- **VPS con `nginx` + `systemd`**: backend en `127.0.0.1:8184` y frontend en `127.0.0.1:3101`, publicados por `nginx` en `asistenciamodelo.online`.

## Docker Compose local
```bash
docker compose up --build
```

Este flujo es alterno al arranque manual y usa los puertos definidos en `docker-compose.yml`.

## Roadmap inmediato
- Vincular autenticación por correo corporativo y RBAC jerárquico (empleado, director,
  rector).
- Implementar pipeline de características (punctuality score, rankings, anomalías).
- Conectar con Vertex AI (Gemini 1.5) para generar feedback natural y reportes ejecutivos.
- Publicar dashboards exportables (PDF/CSV) y alertas programadas.

## Deploy VPS
- La preparación de producción con `nginx`, `systemd` y `certbot` está documentada en `docs/deploy-vps-nginx-systemd-certbot.md`.
- El despliegue recomendado usa `127.0.0.1:8184` para backend y `127.0.0.1:3101` para frontend, quedando publicado solo por `nginx` en `asistenciamodelo.online`.
- El `frontend.env` de producción debe incluir `AUTH_SECRET_KEY` con el mismo valor que `backend.env` para evitar una llamada SSR extra a `/auth/me` en cada carga autenticada.

## Documentacion tecnica relevante
- El flujo exacto de importacion de `attendance_events` desde Excel esta documentado en `docs/attendance-events-import.md`.
# asistencia
# modeloasist
