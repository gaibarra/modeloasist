from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
import pytest

from app.api.routes.auth import reset_auth_rate_limits
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models import employee_credential  # noqa: F401
from app.models import staff_access  # noqa: F401
from app.models import staff_schedule  # noqa: F401


engine = create_engine(
    "sqlite+pysqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base.metadata.create_all(bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(autouse=True)
def clear_auth_rate_limits():
    reset_auth_rate_limits()
    yield
    reset_auth_rate_limits()
