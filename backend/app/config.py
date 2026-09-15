from pydantic_settings import BaseSettings
from pydantic import model_validator


class Settings(BaseSettings):
    anthropic_api_key: str = ""
    gemini_api_key: str = ""
    openai_api_key: str = ""
    matiec_bin: str = "/usr/local/bin/iec2c"
    # IEC standard library used by iec2c -I (P1-02); the reference image installs it here.
    matiec_lib_dir: str = "/usr/local/share/matiec/lib"
    plcverif_bin: str = "/usr/local/bin/plcverif"
    verification_timeout_s: int = 120
    database_url: str = "sqlite+aiosqlite:///./plcforge.db"

    # LLM Provider Selection
    llm_provider: str = "openai"
    llm_max_tokens: int = 2048
    llm_temperature: float = 0.2

    # Model names per provider
    anthropic_model: str = "claude-sonnet-4-20250514"
    openai_model: str = "gpt-4o"
    gemini_model: str = "gemini-2.0-flash"
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"
    ollama_model: str = "deepseek-coder:33b"

    # Ollama local endpoint
    ollama_base_url: str = "http://localhost:11434"

    max_iter: int = 5

    @model_validator(mode="after")
    def validate_provider_settings(self) -> "Settings":
        provider = self.llm_provider.strip().lower()
        if provider == "anthropic" and not self.anthropic_api_key.strip():
            raise ValueError("ANTHROPIC_API_KEY is required when LLM_PROVIDER=anthropic.")
        if provider == "openai" and not self.openai_api_key.strip():
            raise ValueError("OPENAI_API_KEY is required when LLM_PROVIDER=openai.")
        if provider == "gemini" and not self.gemini_api_key.strip():
            raise ValueError("GEMINI_API_KEY is required when LLM_PROVIDER=gemini.")
        if provider not in {"anthropic", "openai", "gemini", "groq", "ollama"}:
            raise ValueError(
                f"Unsupported LLM_PROVIDER '{self.llm_provider}'. Supported providers: anthropic, openai, gemini, groq, ollama."
            )
        return self

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
