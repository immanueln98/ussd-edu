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
    
    # Groq LLM (Phase 2)
    groq_api_key: str = ""
    llm_model: str = "llama-3.1-8b-instant"
    llm_timeout: int = 10  # seconds
    llm_max_tokens: int = 500

    # Chat Configuration (Phase 3)
    chat_timeout: int = 6                    # Tighter timeout for USSD chat (seconds)
    chat_context_turns: int = 3              # Number of previous turns to include in context
    chat_max_response_chars: int = 90        # Target response length for USSD display
    chat_hard_truncate_chars: int = 95       # Absolute maximum before truncation
    chat_llm_max_tokens: int = 60            # Limit output tokens for faster response
    chat_llm_temperature: float = 0.5        # Lower temperature for more consistent responses

    # App Settings
    debug: bool = True
    session_timeout: int = 300  # 5 minutes
    max_ussd_chars: int = 160

    # Feature Flags
    use_llm_quiz: bool = True   # Set to False to use pre-stored questions
    use_llm_chat: bool = True   # Set to False to use static fallback responses

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
