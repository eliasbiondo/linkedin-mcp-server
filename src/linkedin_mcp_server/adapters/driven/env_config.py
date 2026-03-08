"""Environment config adapter — ConfigPort implementation.

Loads configuration from defaults → .env → environment variables → CLI args.
"""

import argparse
import logging
import os
from pathlib import Path

from dotenv import load_dotenv

from linkedin_mcp_server.domain.value_objects import (
    AppConfig,
    BrowserConfig,
    ServerConfig,
)
from linkedin_mcp_server.ports.config import ConfigPort

logger = logging.getLogger(__name__)


class EnvConfigAdapter(ConfigPort):
    """ConfigPort implementation: .env + env vars + CLI args."""

    def __init__(self, cli_args: argparse.Namespace | None = None):
        self._cli_args = cli_args

    def load(self) -> AppConfig:
        """Load config with precedence: CLI > env > .env > defaults."""
        # Load .env files
        load_dotenv()
        for env_path in [".env.local", ".env"]:
            if Path(env_path).exists():
                load_dotenv(env_path, override=True)

        # Determine headless (CLI > env > default)
        headless = self._get_bool("LINKEDIN_HEADLESS", True)
        if (
            self._cli_args
            and hasattr(self._cli_args, "headless")
            and self._cli_args.headless is not None
        ):
            headless = self._cli_args.headless

        browser_config = BrowserConfig(
            headless=headless,
            slow_mo=self._get_int("LINKEDIN_SLOW_MO", 0),
            user_agent=os.environ.get("LINKEDIN_USER_AGENT"),
            viewport_width=self._get_int("LINKEDIN_VIEWPORT_WIDTH", 1280),
            viewport_height=self._get_int("LINKEDIN_VIEWPORT_HEIGHT", 720),
            default_timeout=self._get_int("LINKEDIN_TIMEOUT", 10000),
            chrome_path=os.environ.get("LINKEDIN_CHROME_PATH"),
            user_data_dir=os.environ.get(
                "LINKEDIN_USER_DATA_DIR", "~/.linkedin-mcp-server/browser-data"
            ),
        )

        # Determine transport from CLI or env
        transport = os.environ.get("LINKEDIN_TRANSPORT", "stdio")
        transport_explicitly_set = False
        if self._cli_args and hasattr(self._cli_args, "transport") and self._cli_args.transport:
            transport = self._cli_args.transport
            transport_explicitly_set = True

        # Determine log level
        log_level = os.environ.get("LINKEDIN_LOG_LEVEL", "WARNING").upper()
        if self._cli_args and hasattr(self._cli_args, "log_level") and self._cli_args.log_level:
            log_level = self._cli_args.log_level.upper()

        # Determine host and port (CLI > env > default)
        host = os.environ.get("LINKEDIN_HOST", "127.0.0.1")
        if self._cli_args and hasattr(self._cli_args, "host") and self._cli_args.host:
            host = self._cli_args.host

        port = self._get_int("LINKEDIN_PORT", 8000)
        if self._cli_args and hasattr(self._cli_args, "port") and self._cli_args.port is not None:
            port = self._cli_args.port

        server_config = ServerConfig(
            transport=transport,  # type: ignore[arg-type]
            transport_explicitly_set=transport_explicitly_set,
            log_level=log_level,  # type: ignore[arg-type]
            login=getattr(self._cli_args, "login", False),
            status=getattr(self._cli_args, "status", False),
            logout=getattr(self._cli_args, "logout", False),
            host=host,
            port=port,
            path=os.environ.get("LINKEDIN_PATH", "/mcp"),
        )

        is_interactive = getattr(self._cli_args, "interactive", False)

        return AppConfig(
            browser=browser_config,
            server=server_config,
            is_interactive=is_interactive,
        )

    @staticmethod
    def _get_bool(key: str, default: bool) -> bool:
        """Get a boolean from environment variable."""
        val = os.environ.get(key)
        if val is None:
            return default
        return val.lower() in ("true", "1", "yes")

    @staticmethod
    def _get_int(key: str, default: int) -> int:
        """Get an integer from environment variable."""
        val = os.environ.get(key)
        if val is None:
            return default
        try:
            return int(val)
        except ValueError:
            logger.warning("Invalid integer for %s: %s, using default %d", key, val, default)
            return default
