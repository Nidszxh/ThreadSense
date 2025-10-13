from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "ThreadSense API"
    app_version: str = "0.1.0"
    environment: str = "development"

    database_url: str = (
        "postgresql+psycopg://threadsense:threadsense@localhost:5432/threadsense"
    )
    redis_url: str = "redis://localhost:6379/0"

    llm_api_key: str | None = None
    llm_base_url: str = "https://api.openai.com/v1"
    llm_model: str = "gpt-4o-mini"
    llm_json_mode: bool = True
    llm_timeout_seconds: float = 120.0
    llm_max_branches: int = 12
    llm_summary_max_chars: int = 30000
    llm_max_comment_chars: int = 200
    llm_max_comments_per_branch: int = 40

    reddit_client_id: str = ""
    reddit_client_secret: str = ""
    reddit_username: str = ""
    reddit_password: str = ""
    reddit_user_agent: str = "threadsense:dev:v0.1"


@lru_cache
def get_settings() -> Settings:
    return Settings()
