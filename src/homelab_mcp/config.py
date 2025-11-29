"""Configuration management for homelab MCP server."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Proxmox connection settings
    proxmox_host: str = "localhost"
    proxmox_port: int = 8006
    proxmox_verify_ssl: bool = False  # Set to True in production with valid certs

    # Authentication - Use API token (recommended) or username/password
    proxmox_api_token_id: str | None = None  # Format: user@realm!tokenid
    proxmox_api_token_secret: str | None = None

    # Alternative: username/password auth (less secure, avoid if possible)
    proxmox_username: str | None = None
    proxmox_password: str | None = None
    proxmox_realm: str = "pam"  # pam, pve, or custom realm

    # MCP Server settings
    mcp_server_host: str = "0.0.0.0"
    mcp_server_port: int = 8080

    @property
    def proxmox_base_url(self) -> str:
        """Construct the Proxmox API base URL."""
        return f"https://{self.proxmox_host}:{self.proxmox_port}/api2/json"

    @property
    def use_api_token(self) -> bool:
        """Check if API token authentication is configured."""
        return bool(self.proxmox_api_token_id and self.proxmox_api_token_secret)


settings = Settings()
