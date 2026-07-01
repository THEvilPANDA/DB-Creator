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
    ADMIN_KEY: str = ""
    JWT_SECRET: str = ""
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60
    JWT_REFRESH_EXPIRE_DAYS: int = 7
    DEFAULT_ADMIN_PASSWORD: str = ""


def _validate_settings(s: Settings) -> Settings:
    errors = []
    if not s.JWT_SECRET:
        errors.append("JWT_SECRET is not set — generate with: python -c \"import secrets; print(secrets.token_hex(32))\"")
    if not s.FERNET_KEY:
        errors.append("FERNET_KEY is not set — generate with: python -c \"import os,base64; print(base64.urlsafe_b64encode(os.urandom(32)).decode())\"")
    if errors:
        raise RuntimeError("Missing required configuration:\n  " + "\n  ".join(errors))
    return s


settings = _validate_settings(Settings())
