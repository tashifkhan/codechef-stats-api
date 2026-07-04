import os

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "CodeChef API"
    app_version: str = "0.1.0"
    codechef_base_url: str = "https://www.codechef.com"
    request_timeout: float = 120.0
    cache_ttl_seconds: int = 300
    cache_max_entries: int = 256
    rate_limit_requests: int = 60
    rate_limit_window_seconds: int = 60
    redis_url: str | None = os.getenv("REDIS_URL")
    upstash_redis_rest_url: str | None = os.getenv("UPSTASH_REDIS_REST_URL")
    upstash_redis_rest_token: str | None = os.getenv("UPSTASH_REDIS_REST_TOKEN")
    api_cache_ttl_seconds: int = int(os.getenv("API_CACHE_TTL_SECONDS", "3600"))
    invalid_user_cache_ttl_seconds: int = int(os.getenv("INVALID_USER_CACHE_TTL_SECONDS", "300"))
    rate_limit_ip_requests: int = int(os.getenv("RATE_LIMIT_IP_REQUESTS", "60"))
    rate_limit_handle_requests: int = int(os.getenv("RATE_LIMIT_HANDLE_REQUESTS", "30"))
    invalid_rate_limit_ip_requests: int = int(os.getenv("INVALID_RATE_LIMIT_IP_REQUESTS", "10"))
    invalid_rate_limit_handle_requests: int = int(os.getenv("INVALID_RATE_LIMIT_HANDLE_REQUESTS", "5"))
    invalid_rate_limit_window_seconds: int = int(os.getenv("INVALID_RATE_LIMIT_WINDOW_SECONDS", "600"))
    rate_limit_backoff_base_seconds: int = int(os.getenv("RATE_LIMIT_BACKOFF_BASE_SECONDS", "5"))
    rate_limit_backoff_max_seconds: int = int(os.getenv("RATE_LIMIT_BACKOFF_MAX_SECONDS", "300"))
    user_agent: str = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )

    model_config = SettingsConfigDict(env_prefix="CODECHEF_", extra="ignore")


settings = Settings()
