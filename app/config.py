from pydantic import Field, field_serializer, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

MASK = "***"

DEFAULT_MAX_UPLOAD_SIZE_BYTES = 100 * 1024 * 1024

DEFAULT_LOG_FILE = "storage/logs/app.log"


class Settings(BaseSettings):
    """Central application configuration loaded from the environment and .env.

    This is the single place where environment variables are read. Secrets are
    never logged or repr()'d: repr is overridden so DATABASE_URL is masked.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    DATABASE_URL: str = Field(
        ...,
        description="SQLAlchemy URL of the PostgreSQL database.",
    )
    STORAGE_ROOT: str = Field(
        default="storage",
        description="Root directory for locally stored document files.",
    )
    MAX_UPLOAD_SIZE_BYTES: int = Field(
        default=DEFAULT_MAX_UPLOAD_SIZE_BYTES,
        description="Maximum accepted upload size in bytes.",
    )
    LOG_FILE: str = Field(
        default=DEFAULT_LOG_FILE,
        description="Path of the persistent JSON Lines application journal.",
    )

    @field_validator("DATABASE_URL")
    @classmethod
    def _database_url_not_empty(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("DATABASE_URL must not be empty")
        return value.strip()

    @field_validator("STORAGE_ROOT")
    @classmethod
    def _storage_root_not_empty(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("STORAGE_ROOT must not be empty")
        return value.strip()

    @field_validator("MAX_UPLOAD_SIZE_BYTES")
    @classmethod
    def _upload_size_positive(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("MAX_UPLOAD_SIZE_BYTES must be greater than 0")
        return value

    @field_validator("LOG_FILE")
    @classmethod
    def _log_file_not_empty(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("LOG_FILE must not be empty")
        return value.strip()

    @field_serializer("DATABASE_URL")
    def _mask_database_url(self, value: str) -> str:
        """Mask the URL in serialized output so it cannot leak into logs."""
        return MASK

    def __repr__(self) -> str:  # pragma: no cover - trivial formatting
        return (
            f"{type(self).__name__}("
            f"DATABASE_URL={MASK!r}, "
            f"STORAGE_ROOT={self.STORAGE_ROOT!r}, "
            f"MAX_UPLOAD_SIZE_BYTES={self.MAX_UPLOAD_SIZE_BYTES!r}, "
            f"LOG_FILE={self.LOG_FILE!r})"
        )

    __str__ = __repr__


def get_settings() -> Settings:
    """Build settings from the current environment / .env file."""
    return Settings()  # type: ignore[call-arg]