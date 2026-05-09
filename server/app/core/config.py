from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "LAN Pulse"
    client_min_version: str = "0.1.0"
    database_url: str = "sqlite+aiosqlite:///./lanpulse.db"
    public_base_url: str = "http://localhost:8080"
    udp_echo_host: str = "0.0.0.0"
    udp_echo_port: int = 8090
    metrics_interval_seconds: int = 2
    client_offline_after_seconds: int = 10
    retention_days: int = 7
    event_retention_days: int = 30
    game_server_host: str | None = None
    downloads_dir: Path = Field(default=Path("/app/downloads"))
    web_dist_dir: Path = Field(default=Path("/app/web-dist"))


settings = Settings()
