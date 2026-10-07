# Asistencia Backend

FastAPI service that exposes attendance analytics APIs, orchestrates AI insights with Google
Vertex AI, and interfaces with the existing PostgreSQL `asistencia` database.

## Features
- REST + future GraphQL endpoints for attendance insights
- SQLAlchemy ORM models reflecting `employees`, `schedules`, and `attendance_events`
- Staff authentication with department-scoped access for mobile daily attendance queries
- Normalized department catalog plus staff-to-department scope tables
- Dependency-injected session management and configuration control
- Placeholder service for Vertex AI prompts that can be wired to Gemini 1.5 Pro
- Ready for Alembic migrations and background analytics jobs

## Local development
1. Create a virtual environment for Python 3.11+ and install dependencies:
   ```bash
   cd backend
   python -m venv .venv && source .venv/bin/activate
   pip install .[dev]
   ```
2. Provide environment variables (see `.env.example`) and point `DATABASE_URL` to PostgreSQL.
3. Run the API locally:
   ```bash
   uvicorn app.main:app --reload --port 8081
   ```
4. Execute tests:
   ```bash
   pytest
   ```

## Alembic migrations
Run migrations from `backend/` so Alembic can read `.env` and resolve the `app` package correctly.

Important for the current PostgreSQL setup: the DB user must be able to create tables in schema `public`. Without that privilege, `alembic upgrade head` cannot create `alembic_version`, `departments`, or the new staff access tables.

```bash
.venv/bin/alembic -c alembic.ini heads
.venv/bin/alembic -c alembic.ini upgrade head
.venv/bin/alembic -c alembic.ini revision -m "describe change"
```

Current baseline revision for the staff feature:
- `20260320_0001`: creates `staff_users`, `departments`, `department_aliases`, `employee_departments`, and `staff_department_scopes`

## Runtime ports
- `8081`: local manual development with `backend/.env`
- `8080`: local containerized flow via `docker-compose.yml`
- `8184`: production/VPS behind `nginx` and `systemd`

## New staff endpoints
- `POST /auth/login`: supports both employee and staff credentials
- `GET /staff/departments`: lists normalized departments for superadmin flows
- `GET /staff/users`: lists current staff users and their scoped departments
- `POST /staff/users`: creates a staff account with optional employee link and department scopes
- `PUT /staff/users/{id}/departments`: replaces the department scopes of a staff user
- `GET /staff/mobile/daily`: mobile-friendly daily attendance query scoped by department

## Next steps
- Connect to managed PostgreSQL or Cloud SQL via SQLAlchemy URL.
- Decide when to retire bootstrap-created tables and rely exclusively on Alembic in every environment.
- Replace the Vertex AI stub with actual SDK calls and observability hooks.

## Contratos laborales: importación revisada

El módulo `app.services.labor_contract_import` importa únicamente datos operativos y
horas semanales. No importa RFC, CURP, IMSS ni fecha de alta; tampoco cambia horarios,
contraseñas o eventos. Requiere confirmar una vista previa antes de escribir.

Desde `backend`, generar la revisión sin escrituras en la base:

```bash
.venv/bin/python -m app.services.labor_contract_import preview \
  --source '../cem don gonzalo.xlsx' \
  --output '../reportes/contratos-2026-S2/revision.json'
```

Genera JSON y Excel con permisos `0600`. La hoja de mapeo propone referencias, no
asignaciones automáticas. Para incorporar decisiones humanas, `--mapping` acepta:

```json
{"department_map": {"universidad:CODIGO_ORIGEN": 123}, "confirmed_matches": {"universidad:2": 456}}
```

Los números son ejemplos: deben reemplazarse por IDs verificados de la aplicación.
Después de cada decisión o cambio de catálogo, generar y confirmar otra vista previa.
La vigencia de esta importación está fijada a 2026-08-01 / 2026-12-31.

Antes de aplicar: respaldar PostgreSQL y aplicar exclusivamente la migración
`20261007_0015` con el entorno correcto. La importación no migra automáticamente.
No usar el script de redeploy fijado a `7bd4080` para publicar estos cambios nuevos.

Tras aprobación, crear un JSON con las claves exactas de las filas autorizadas,
por ejemplo `["universidad:2"]`. Ejecutar con un staff superadministrador activo:

```bash
.venv/bin/python -m app.services.labor_contract_import apply \
  --source '../cem don gonzalo.xlsx' --preview '../reportes/contratos-2026-S2/revision.json' \
  --approved '../reportes/contratos-2026-S2/aprobadas.json' --staff-id ID_VERIFICADO \
  --backup '../reportes/contratos-2026-S2/antes-aplicar.dump'
```

El respaldo debe ser una ruta nueva; el comando ejecuta `pg_dump` y verifica su
catálogo antes de comenzar la transacción. No imprime credenciales. Rechaza cambios
concurrentes, duplicaciones, filas ambiguas y contratos de vigencias solapadas.
Los valores vacíos no borran contratos anteriores. Repetir la misma operación no
crea otra importación. La reversión conserva la bitácora y no pisa cambios posteriores:

```bash
.venv/bin/python -m app.services.labor_contract_import rollback \
  --import-id ID_OPERACION --staff-id ID_VERIFICADO \
  --backup '../reportes/contratos-2026-S2/antes-revertir.dump'
```

`GET /staff/labor-contracts` permite consulta y CSV (`export=true`) con alcance de
staff. Filtros: `department_id`, `employee_id` (requiere departamento), `campus`,
`contract_status`, `academic_year`, `semester`. No hay API pública de importación.
`GET /staff/weekly-hours` conserva sus campos anteriores y agrega
`labor_contract_seconds`, `scheduled_seconds`, `scheduled_contract_difference_seconds`
y `worked_scheduled_difference_seconds`. El campo histórico `contracted_seconds`
sigue representando horas programadas; no debe interpretarse como contrato laboral.
