from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    app_name: str = "FinancePay"
    environment: str = "development"
    api_prefix: str = "/api"
    secret_key: str = Field(default="change-me-before-production", min_length=12)
    access_token_expire_minutes: int = 30
    refresh_token_expire_minutes: int = 60 * 24 * 30
    cushion_token_expire_minutes: int = 20

    database_url: str = "postgresql+asyncpg://financepay:financepay@localhost:5432/financepay"
    backend_cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    backend_cors_origin_regex: str | None = (
        r"^http://(localhost|127\.0\.0\.1|0\.0\.0\.0|10\.\d+\.\d+\.\d+|"
        r"192\.168\.\d+\.\d+|172\.(1[6-9]|2\d|3[0-1])\.\d+\.\d+):\d+$"
    )

    gemini_api_key: str | None = None
    gemini_model: str = "gemini-flash-latest"
    gemini_api_base_url: str = "https://generativelanguage.googleapis.com/v1beta"
    gemini_timeout_seconds: int = 30

    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_from: str = "no-reply@financepay.local"
    smtp_use_tls: bool = True

    mailru_client_id: str | None = None
    mailru_client_secret: str | None = None
    mailru_redirect_uri: str = "http://localhost:8000/api/mail/oauth/callback"
    mailru_auth_url: str = "https://oauth.mail.ru/login"
    mailru_token_url: str = "https://oauth.mail.ru/token"
    mailru_scope: str = "userinfo mail.imap"
    mail_imap_host: str = "imap.mail.ru"
    mail_imap_port: int = 993
    mail_imap_ssl: bool = True

    payment_service_url: str = "http://localhost:8001"
    payment_callback_url: str = "http://127.0.0.1:8000/api/payments/sbp/callback"
    receipt_parse_delay_seconds: int = 60
    timezone: str = "Europe/Moscow"
    demo_mode: bool = True

    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.backend_cors_origins.split(",") if origin.strip()]

    @property
    def is_gemini_enabled(self) -> bool:
        return bool(self.gemini_api_key)

    @property
    def is_smtp_enabled(self) -> bool:
        return bool(self.smtp_host and self.smtp_username and self.smtp_password)

    @property
    def is_mailru_oauth_enabled(self) -> bool:
        return bool(self.mailru_client_id and self.mailru_client_secret)


@lru_cache
def get_settings() -> Settings:
    return Settings()
