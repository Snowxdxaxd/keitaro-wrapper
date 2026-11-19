"""Настройки обёртки: читаются из .env / окружения."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    keitaro_base_url: str = "https://tlgk.host"
    keitaro_api_key: str = ""

    keitaro_group_name: str = "FORTESTS"
    keitaro_source_name: str = "FORTESTS"

    campaign_name_prefix: str = "test_mkrtchyan_"
    google_redirect_url: str = "https://google.com"

    database_url: str = "sqlite:///./app.db"


settings = Settings()
