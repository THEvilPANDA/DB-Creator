from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str = "postgresql+asyncpg://dbcreator:dbcreator@localhost:5432/dbcreator"
    TEST_DATABASE_URL: str = "postgresql+asyncpg://dbcreator:dbcreator@localhost:5432/dbcreator_test"
    REDIS_URL: str = "redis://localhost:6379/0"
    FERNET_KEY: str = ""
    DEBUG: bool = False
    ENVIRONMENT: str = "development"


settings = Settings()
