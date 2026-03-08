"""Immutable value objects for configuration and content passing between layers."""

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class SectionConfig:
    """Configuration for a scrapeable LinkedIn section."""

    name: str
    url_suffix: str
    is_overlay: bool = False


@dataclass(frozen=True)
class PageContent:
    """Extracted content from a LinkedIn page."""

    url: str
    html: str
    is_rate_limited: bool = False


@dataclass(frozen=True)
class BrowserConfig:
    """Browser configuration values."""

    headless: bool = True
    slow_mo: int = 0
    user_agent: str | None = None
    viewport_width: int = 1280
    viewport_height: int = 720
    default_timeout: int = 10000
    chrome_path: str | None = None
    user_data_dir: str = "~/.linkedin-mcp-server/browser-data"


@dataclass(frozen=True)
class ServerConfig:
    """MCP server configuration values."""

    transport: Literal["stdio", "streamable-http"] = "stdio"
    transport_explicitly_set: bool = False
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "WARNING"
    login: bool = False
    status: bool = False
    logout: bool = False
    host: str = "127.0.0.1"
    port: int = 8000
    path: str = "/mcp"


@dataclass(frozen=True)
class AppConfig:
    """Complete application configuration."""

    browser: BrowserConfig = BrowserConfig()  # type: ignore[call-arg]
    server: ServerConfig = ServerConfig()  # type: ignore[call-arg]
    is_interactive: bool = False
