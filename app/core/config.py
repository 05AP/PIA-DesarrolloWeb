from typing import List

from pydantic import EmailStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_SECRET_KEY = "gasolinera_super_secret_key_change_in_production_2026"


class Settings(BaseSettings):
    PROJECT_NAME: str = "Gasolinera API"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    ENVIRONMENT: str = "development"
    DEBUG: bool = False  # Si es True, SQLAlchemy imprime cada consulta SQL

    # Database
    DATABASE_URL: str = "sqlite:///./gasolinera.db"

    # JWT Security
    SECRET_KEY: str = DEFAULT_SECRET_KEY
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480  # 8 horas de turno de trabajo

    # CORS: orígenes externos autorizados (el frontend integrado se sirve desde el mismo origen).
    # En .env se define como JSON: BACKEND_CORS_ORIGINS='["https://mi-frontend.com"]'
    BACKEND_CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:8000",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:8000",
    ]

    # Superuser inicial para seeding
    FIRST_SUPERUSER_EMAIL: EmailStr = "admin@gasolinera.com"
    FIRST_SUPERUSER_PASSWORD: str = "admin123"
    FIRST_SUPERUSER_NAME: str = "Administrador General"

    # Siembra usuarios demo (supervisor/despachador), catálogo y transacciones de ejemplo
    SEED_DEMO_DATA: bool = True

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT.lower() == "production"

    @model_validator(mode="after")
    def validate_production_secrets(self):
        """Fail-fast: impide arrancar en producción con la clave JWT de ejemplo."""
        if self.is_production and (self.SECRET_KEY == DEFAULT_SECRET_KEY or len(self.SECRET_KEY) < 32):
            raise ValueError(
                "SECRET_KEY inseguro: en producción debe definirse una clave propia de al menos 32 caracteres."
            )
        return self


settings = Settings()
