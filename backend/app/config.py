from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration loaded from environment variables and backend/.env."""

    anthropic_api_key: SecretStr | None = Field(default=None, alias="ANTHROPIC_API_KEY")
    matiec_bin: Path = Field(default=Path("/usr/local/bin/iec2c"), alias="MATIEC_BIN")
    plcverif_bin: Path = Field(default=Path("/usr/local/bin/plcverif"), alias="PLCVERIF_BIN")
    database_url: str = Field(default="sqlite+aiosqlite:///./plcforge.db", alias="DATABASE_URL")
    llm_provider: Literal["anthropic"] = Field(default="anthropic", alias="LLM_PROVIDER")
    max_iter: int = Field(default=5, ge=1, le=25, alias="MAX_ITER")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
        case_sensitive=False,
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
