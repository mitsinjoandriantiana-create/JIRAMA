from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "JIRAMA Invoice Manager"
    secret_key: str = "development-only-change-this-secret"
    database_url: str = "sqlite:///./jirama.db"
    upload_dir: str = "uploads"
    access_token_expire_minutes: int = 60
    streamlit_url: str = "http://127.0.0.1:8501"

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )


settings = Settings()
