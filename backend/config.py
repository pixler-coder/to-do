"""
Centralized application settings.

Reads from environment variables and an optional `.env` file.
See `.env.example` for available configuration options.
"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    database_url: str = "sqlite:///./todo.db"

    # CORS — comma-separated origins
    allowed_origins: str = "http://127.0.0.1:8000,http://localhost:8000"

    # Debug mode — controls interactive API docs visibility
    debug: bool = True

    # Logging
    log_level: str = "INFO"

    @property
    def cors_origins(self) -> list[str]:
        """Parse the comma-separated origins string into a list."""
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
    }


# Singleton instance — imported throughout the app
settings = Settings()
