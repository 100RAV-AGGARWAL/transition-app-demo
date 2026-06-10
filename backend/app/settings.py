from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Transition Support Portal"
    environment: str = "local"
    api_prefix: str = "/api"
    frontend_origin: str = "https://project-libyg.vercel.app/"

    database_url: str = Field(
        default="postgresql+asyncpg://app:app@localhost:5432/transition_portal",
        description="Use the Amazon RDS PostgreSQL URL in higher environments.",
    )

    # Development auth is header based. Replace with Cognito, Entra ID, Okta, or Auth0 in production.
    dev_auth_enabled: bool = True

    mock_integrations: bool = True
    default_timezone: str = "Asia/Kolkata"
    slot_interval_minutes: int = 30
    default_call_duration_minutes: int = 30
    business_day_start_hour: int = 9
    business_day_end_hour: int = 17

    training_api_base_url: str | None = None
    training_api_key: str | None = None

    microsoft_tenant_id: str | None = None
    microsoft_client_id: str | None = None
    microsoft_client_secret: str | None = None

    zoom_account_id: str | None = None
    zoom_client_id: str | None = None
    zoom_client_secret: str | None = None

    notification_from_email: str = "no-reply@example.com"


@lru_cache
def get_settings() -> Settings:
    return Settings()
