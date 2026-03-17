"""Application configuration loaded from environment variables."""

from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    # Azure Entra ID
    azure_client_id: str = ""
    azure_tenant_id: str = "common"
    azure_client_secret: str = ""

    # Microsoft Graph
    graph_base_url: str = "https://graph.microsoft.com/v1.0"
    graph_scopes: list[str] = [
        "Files.ReadWrite",
        "Mail.Send",
        "Mail.Read",
        "User.Read",
    ]

    # OneDrive
    onedrive_file_path: str = ""

    # App settings
    app_host: str = "127.0.0.1"
    app_port: int = 8000
    follow_up_days: int = 7
    max_follow_ups: int = 2
    send_rate_limit_delay: float = 2.0  # seconds between emails
    inbox_check_interval_minutes: int = 30

    # Local file mode — bypass OneDrive, use local xlsx for testing
    use_local_file: bool = False

    # Database
    database_url: str = "sqlite:///./outreach.db"
    database_path: str = "./outreach.db"

    # Token cache
    token_cache_path: str = "./.token_cache.json"

    model_config = {
        "env_file": "../.env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


settings = Settings()
