"""Application configuration loaded from environment variables (and an optional .env file)."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, computed_field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(BACKEND_DIR.parent / ".env", BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- Application ---
    APP_NAME: str = "Healthcare Appointment No-Show Prediction System"
    ENVIRONMENT: Literal["development", "staging", "production"] = "development"
    LOG_LEVEL: str = "INFO"
    API_PREFIX: str = "/api"
    CORS_ORIGINS: list[str] = Field(default_factory=lambda: ["http://localhost:5173", "http://localhost:3000"])

    # --- Database (DATABASE_URL wins if provided, otherwise it is built from the POSTGRES_* parts) ---
    DATABASE_URL: str | None = None
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = ""
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "hospital_noshow"

    # --- Security ---
    JWT_SECRET_KEY: str = Field(..., min_length=32)
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480
    FIRST_ADMIN_EMAIL: str | None = None
    FIRST_ADMIN_PASSWORD: str | None = None
    FIRST_ADMIN_NAME: str = "System Administrator"
    # Optional: seed demo STAFF / DOCTOR accounts with this password (skipped when unset)
    DEMO_USERS_PASSWORD: str | None = None

    # --- Machine learning ---
    MODEL_DIR: Path = BACKEND_DIR / "models"
    DATA_DIR: Path = BACKEND_DIR / "data"
    RISK_LOW_MAX: float = Field(0.30, gt=0, lt=1)
    RISK_MEDIUM_MAX: float = Field(0.60, gt=0, lt=1)
    AUTO_PREDICT_ON_BOOKING: bool = True

    # --- GenAI (provider-agnostic) ---
    LLM_PROVIDER: Literal["anthropic", "openai", "none"] = "none"
    LLM_API_KEY: str | None = None
    LLM_MODEL: str | None = None
    LLM_BASE_URL: str | None = None
    LLM_TIMEOUT_SECONDS: float = 90.0
    LLM_MAX_TOKENS: int = 16000
    LLM_TEMPERATURE: float = 0.3  # used by OpenAI-compatible providers only
    LLM_EFFORT: Literal["low", "medium", "high", "xhigh", "max"] = "medium"  # Anthropic output_config.effort

    # --- Hospital details used in patient reminders ---
    HOSPITAL_NAME: str = "City General Hospital"
    HOSPITAL_PHONE: str = "+1-555-0100"

    @model_validator(mode="after")
    def _check_thresholds(self) -> "Settings":
        if self.RISK_LOW_MAX >= self.RISK_MEDIUM_MAX:
            raise ValueError("RISK_LOW_MAX must be lower than RISK_MEDIUM_MAX")
        return self

    @computed_field  # type: ignore[prop-decorator]
    @property
    def sqlalchemy_database_url(self) -> str:
        if self.DATABASE_URL:
            url = self.DATABASE_URL
            if url.startswith("postgresql://"):
                url = url.replace("postgresql://", "postgresql+psycopg://", 1)
            return url
        return (
            f"postgresql+psycopg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def model_path(self) -> Path:
        return self.MODEL_DIR / "no_show_model.pkl"

    @property
    def metrics_path(self) -> Path:
        return self.MODEL_DIR / "metrics.json"

    @property
    def dataset_path(self) -> Path:
        return self.DATA_DIR / "appointments.csv"


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
