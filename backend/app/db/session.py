"""Database engine and session factory."""
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

_SETTINGS = get_settings()

engine_kwargs: dict[str, object] = {"pool_pre_ping": True}
if _SETTINGS.database_url.startswith("sqlite"):
    engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    engine_kwargs.update({"pool_size": 5, "max_overflow": 5})

engine = create_engine(_SETTINGS.database_url, **engine_kwargs)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    """Provide a DB session for request scope."""

    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
