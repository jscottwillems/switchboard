"""Process settings loaded from the environment."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration for the telephony slice.

    Environment variables use the SWITCHBOARD_ prefix. Example:
    SWITCHBOARD_PUBLIC_BASE_URL=https://pbx.example.com
    """

    model_config = SettingsConfigDict(
        env_prefix="SWITCHBOARD_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    public_base_url: str = "http://localhost:8000"
    media_ws_base_url: str = "ws://localhost:8000"
    mock_webhook_secret: str = "dev-mock-secret"
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    log_level: str = "INFO"
    default_mock_secret: str = Field(default="dev-mock-secret")

    def media_stream_url(self, provider: str) -> str:
        base = self.media_ws_base_url.rstrip("/")
        return f"{base}/media/stream/{provider}"

    def public_url(self, path: str) -> str:
        base = self.public_base_url.rstrip("/")
        if not path.startswith("/"):
            path = "/" + path
        return base + path
