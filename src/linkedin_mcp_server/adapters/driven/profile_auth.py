"""Profile auth adapter — AuthPort implementation using persistent browser profile."""

import asyncio
import contextlib
import logging
import shutil
from pathlib import Path

from linkedin_mcp_server.domain.exceptions import AuthenticationError
from linkedin_mcp_server.domain.value_objects import BrowserConfig
from linkedin_mcp_server.ports.auth import AuthPort
from linkedin_mcp_server.ports.browser import BrowserPort

logger = logging.getLogger(__name__)

_LOGIN_TIMEOUT_S = 300  # 5 minutes to complete login
_LOGIN_POLL_INTERVAL_S = 2  # Check every 2 seconds

_AUTH_BLOCKER_PATTERNS = [
    "/login",
    "/authwall",
    "/checkpoint",
    "/challenge",
    "/uas/login",
    "/uas/consumer-email-challenge",
]

_AUTHENTICATED_PAGE_PATTERNS = [
    "/feed",
    "/mynetwork",
    "/messaging",
    "/notifications",
]

_WARM_UP_SITES = [
    "https://www.bing.com",
    "https://www.reddit.com",
    "https://www.stackoverflow.com",
]


class ProfileAuthAdapter(AuthPort):
    """AuthPort implementation using persistent Patchright browser profile."""

    def __init__(self, browser: BrowserPort, config: BrowserConfig):
        self._browser = browser
        self._config = config

    async def is_authenticated(self) -> bool:
        """Check login status by navigating to LinkedIn feed and inspecting the URL."""
        try:
            await self._browser.navigate("https://www.linkedin.com/feed/")
            url = await self._browser.get_current_url()

            # Fail-fast on auth blocker URLs
            if any(pattern in url for pattern in _AUTH_BLOCKER_PATTERNS):
                return False

            # Authenticated pages confirm login
            return any(pattern in url for pattern in _AUTHENTICATED_PAGE_PATTERNS)
        except Exception as e:
            logger.warning("Auth check failed: %s", e)
            return False

    async def ensure_authenticated(self) -> None:
        """Validate session and raise AuthenticationError if expired."""
        if not await self.is_authenticated():
            raise AuthenticationError(
                "LinkedIn session is not authenticated. "
                "Run with --login to authenticate."
            )

    def has_credentials(self) -> bool:
        """Check if browser profile directory exists and has content."""
        profile_dir = Path(self._config.user_data_dir).expanduser()
        return profile_dir.is_dir() and any(profile_dir.iterdir())

    async def login_interactive(self, warm_up: bool = True) -> bool:
        """Open non-headless browser for manual LinkedIn login.

        Navigates to LinkedIn login, then polls automatically until the user
        completes authentication (including 2FA, captcha, security challenges).
        No manual confirmation needed — login is detected automatically.

        Returns True if login was successful.
        """
        if warm_up:
            print("  Warming up browser...")
            await self._warm_up()

        print("  Navigating to LinkedIn login page...")
        await self._browser.navigate("https://www.linkedin.com/login")

        print(
            f"  Waiting for login (up to {_LOGIN_TIMEOUT_S // 60} minutes)...\n"
            "  Complete authentication in the browser window.\n"
            "  Supports 2FA, captcha, and security challenges.\n"
        )

        authenticated = await self._poll_for_login()

        if not authenticated:
            raise AuthenticationError(
                "Login timed out. Please try again and complete the login faster."
            )

        # Let cookies flush to disk
        await asyncio.sleep(2)

        print("  Login detected! Session saved.\n")
        return True

    async def _warm_up(self) -> None:
        """Visit normal sites to appear more human-like before LinkedIn access."""
        for site in _WARM_UP_SITES:
            with contextlib.suppress(Exception):
                await self._browser.navigate(site)
                await asyncio.sleep(1)

    async def _poll_for_login(self) -> bool:
        """Poll the current URL until login is detected or timeout expires."""
        elapsed = 0.0
        while elapsed < _LOGIN_TIMEOUT_S:
            url = await self._browser.get_current_url()

            # Check if we're on an authenticated page
            if any(pattern in url for pattern in _AUTHENTICATED_PAGE_PATTERNS):
                return True

            # Not on a blocker page but also not on a known auth page?
            # Could be transitioning — keep waiting
            await asyncio.sleep(_LOGIN_POLL_INTERVAL_S)
            elapsed += _LOGIN_POLL_INTERVAL_S

        return False

    async def export_cookies(self) -> bool:
        """Export session cookies for portability."""
        logger.warning("Cookie export not yet implemented")
        return False

    async def import_cookies(self) -> bool:
        """Import session cookies from portable file."""
        logger.warning("Cookie import not yet implemented")
        return False

    def clear_credentials(self) -> bool:
        """Clear stored credentials by removing profile directory."""
        profile_dir = Path(self._config.user_data_dir).expanduser()
        if profile_dir.exists():
            try:
                shutil.rmtree(profile_dir)
                logger.info("Cleared credentials at %s", profile_dir)
                return True
            except Exception as e:
                logger.error("Failed to clear credentials: %s", e)
                return False
        return True

    def get_profile_path(self) -> Path:
        """Return the path to the browser profile directory."""
        return Path(self._config.user_data_dir).expanduser()
