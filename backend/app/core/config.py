"""Application configuration management."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central configuration object loaded from env vars or `.env`."""

    app_env: str = "local"
    api_port: int = 8080
    database_url: str = "sqlite:///./runtime.db"
    ai_project_id: str | None = None
    ai_location: str | None = "us-central1"
    google_application_credentials: str | None = None
    cors_allow_origins: str | None = None
    auth_secret_key: str = "change-me-modeloasist-secret"
    auth_token_ttl_minutes: int = 480
    auth_default_password: str = "CHANGE_ME_TEMPORARY_PASSWORD"
    admin_email: str = "gaibarra@hotmail.com"
    startup_bootstrap_enabled: bool | None = None
    auth_rate_limit_attempts: int = 8
    auth_rate_limit_window_seconds: int = 300

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    def is_production(self) -> bool:
        return self.app_env.strip().lower() == "production"

    def should_run_startup_bootstrap(self) -> bool:
        if self.startup_bootstrap_enabled is not None:
            return self.startup_bootstrap_enabled
        return not self.is_production()

    def validate_runtime_safety(self) -> None:
        if not self.is_production():
            return
        secret = self.auth_secret_key.strip()
        if secret in {"", "change-me-modeloasist-secret"} or "change-me" in secret.lower():
            raise RuntimeError("AUTH_SECRET_KEY debe configurarse con un valor único en producción")
        if self.should_run_startup_bootstrap():
            temporary_password = self.auth_default_password.strip()
            if temporary_password in {"", "CHANGE_ME_TEMPORARY_PASSWORD", "modelo2026"}:
                raise RuntimeError(
                    "AUTH_DEFAULT_PASSWORD debe reemplazarse antes de habilitar el bootstrap en producción"
                )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached settings instance."""

    return Settings()  # type: ignore[arg-type]
