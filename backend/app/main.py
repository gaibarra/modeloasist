"""Entry point for the FastAPI application."""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import get_api_router
from app.core.config import get_settings
from app.db.bootstrap import (
    ensure_employee_auth_schema,
    ensure_staff_access_schema,
    sync_default_employee_passwords,
    sync_default_staff_superadmin,
    sync_department_catalog,
)
from app.db.session import SessionLocal, engine


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings = get_settings()
    if settings.should_run_startup_bootstrap():
        ensure_employee_auth_schema(engine)
        ensure_staff_access_schema(engine)
        db = SessionLocal()
        try:
            sync_default_employee_passwords(db, settings)
            sync_department_catalog(db)
            sync_default_staff_superadmin(db, settings)
        finally:
            db.close()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    settings.validate_runtime_safety()
    app = FastAPI(title="Asistencia Analytics API", version="0.1.0", lifespan=lifespan)
    cors_origins = (
        [origin.strip() for origin in settings.cors_allow_origins.split(",") if origin.strip()]
        if settings.cors_allow_origins
        else ["*"]
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(get_api_router())
    app.state.settings = settings
    return app


app = create_app()
