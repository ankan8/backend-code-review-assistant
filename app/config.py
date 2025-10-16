import os
from functools import lru_cache
from dotenv import load_dotenv

load_dotenv()

class Settings:
    app_env: str = os.getenv("APP_ENV", "dev")
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./reviews.db")

    # LLM config
    openai_api_key: str | None = os.getenv("OPENAI_API_KEY") or None
    openai_base_url: str | None = os.getenv("OPENAI_BASE_URL") or None
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    openai_enabled: bool = (os.getenv("OPENAI_ENABLED", "true").lower() == "true")

    # Prompt size guards (tweak as you like)
    llm_total_chars: int = int(os.getenv("LLM_TOTAL_CHARS", "16000"))    
    llm_per_file_chars: int = int(os.getenv("LLM_PER_FILE_CHARS", "4000")) 

@lru_cache
def get_settings() -> Settings:
    return Settings()
