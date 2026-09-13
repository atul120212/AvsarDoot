from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./avsardoot.db"
    secret_key: str = "dev-secret"
    access_token_expire_minutes: int = 60 * 24 * 7
    encryption_key: str = ""
    admin_email: str = "admin@avsardoot.local"
    admin_password: str = "admin123"
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "alerts@avsardoot.local"
    frontend_url: str = "http://localhost:3000"
    anthropic_api_key: str = ""
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"
    redis_url: str = "redis://localhost:6379/0"
    telegram_bot_token: str = ""
    telegram_bot_username: str = ""  # e.g. avsardoot_bot (without @)



settings = Settings()
