"""Manage browser session lifecycle."""

from linkedin_mcp_server.domain.models.responses import SessionStatus
from linkedin_mcp_server.ports.auth import AuthPort
from linkedin_mcp_server.ports.browser import BrowserPort


class ManageSessionUseCase:
    """Handles session lifecycle operations (login, logout, status, close)."""

    def __init__(self, browser: BrowserPort, auth: AuthPort):
        self._browser = browser
        self._auth = auth

    async def close_browser(self) -> SessionStatus:
        """Close the browser instance and release resources."""
        await self._browser.close()
        return SessionStatus(is_valid=False, message="Browser closed")

    async def check_status(self) -> SessionStatus:
        """Check the current session status."""
        is_valid = await self._auth.is_authenticated()
        return SessionStatus(
            is_valid=is_valid,
            profile_path=str(self._auth.get_profile_path()),
            message="Valid" if is_valid else "Expired",
        )

    async def login(self, warm_up: bool = True) -> SessionStatus:
        """Interactively log in to LinkedIn."""
        success = await self._auth.login_interactive(warm_up=warm_up)
        return SessionStatus(
            is_valid=success,
            profile_path=str(self._auth.get_profile_path()),
            message="Login successful" if success else "Login failed",
        )

    def logout(self) -> SessionStatus:
        """Clear stored credentials."""
        success = self._auth.clear_credentials()
        return SessionStatus(
            is_valid=False,
            message="Credentials cleared" if success else "Failed to clear",
        )
