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
    user_agent: str = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )

    model_config = SettingsConfigDict(env_prefix="CODECHEF_", extra="ignore")


settings = Settings()
