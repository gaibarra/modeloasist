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
