from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "PM Dashboard API"

    postgres_user: str
    postgres_password: str
    postgres_db: str
    postgres_host: str = "localhost"
    postgres_port: int = 5432

    jwt_secret: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    storage_dir: str = "./storage"
    max_file_bytes: int = 10 * 1024 * 1024      # 10 MB per file
    max_project_bytes: int = 50 * 1024 * 1024   # 50 MB per project

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def storage_path(self) -> Path:
        # Resolved once, at import. Relative paths break the moment something
        # runs from a different working directory (alembic, pytest, docker).
        return Path(self.storage_dir).resolve()


ALLOWED_CONTENT_TYPES: dict[str, str] = {
    "application/pdf": ".pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
}

settings = Settings()