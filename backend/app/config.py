from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str = "postgresql+asyncpg://dbcreator:dbcreator@localhost:5432/dbcreator"
    TEST_DATABASE_URL: str = "postgresql+asyncpg://dbcreator:dbcreator@localhost:5432/dbcreator_test"
    REDIS_URL: str = "redis://localhost:6379/0"
    FERNET_KEY: str = ""
    DEBUG: bool = False
    ENVIRONMENT: str = "development"
    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://localhost:5174", "http://localhost:3000"]
    # Set to a strong random secret in production to protect admin endpoints.
    # Phase 7 replaces this with JWT role checks.
    ADMIN_KEY: str = ""
    # JWT — change JWT_SECRET to a long random value in production.
    JWT_SECRET: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60
    JWT_REFRESH_EXPIRE_DAYS: int = 7
    # Seed: set DEFAULT_ADMIN_PASSWORD in .env to create the initial admin on first seed.
    DEFAULT_ADMIN_PASSWORD: str = ""


settings = Settings()
