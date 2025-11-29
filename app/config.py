from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application configuration from environment variables."""
    
    # Africa's Talking
    at_username: str = "sandbox"
    at_api_key: str = ""
    
    # Redis
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    
    # Groq (Phase 2)
    groq_api_key: str = ""
    
    # App Settings
    debug: bool = True
    session_timeout: int = 300  # 5 minutes
    max_ussd_chars: int = 160
    
    # SMS Settings
    sms_sender_id: str = "EduBot"

    # USSD Service Code (for reference)
    ussd_service_code: str = "*384*123#"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    """Cached settings instance."""
    return Settings()
