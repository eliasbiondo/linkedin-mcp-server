"""Auth port — abstracts authentication management."""

from abc import ABC, abstractmethod
from pathlib import Path


class AuthPort(ABC):
    """Port for authentication management."""

    @abstractmethod
    async def is_authenticated(self) -> bool:
        """Check if the current session is authenticated."""
        ...

    @abstractmethod
    async def ensure_authenticated(self) -> None:
        """Validate session and raise AuthenticationError if expired."""
        ...

    @abstractmethod
    def has_credentials(self) -> bool:
        """Check if credentials (browser profile) exist."""
        ...

    @abstractmethod
    async def login_interactive(self, warm_up: bool = True) -> bool:
        """Open browser for manual LinkedIn login.

        Returns True if login was successful.
        """
        ...

    @abstractmethod
    async def export_cookies(self) -> bool:
        """Export session cookies for portability."""
        ...

    @abstractmethod
    async def import_cookies(self) -> bool:
        """Import session cookies from portable file."""
        ...

    @abstractmethod
    def clear_credentials(self) -> bool:
        """Clear stored credentials/profile."""
        ...

    @abstractmethod
    def get_profile_path(self) -> Path:
        """Return the path to the browser profile directory."""
        ...
