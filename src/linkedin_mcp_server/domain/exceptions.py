"""Unified domain exception hierarchy.

All application-specific exceptions derive from LinkedInMCPError.
This replaces the two separate hierarchies from the original codebase.
"""


class LinkedInMCPError(Exception):
    """Base exception for the entire application."""


# ── Authentication ────────────────────────────────────────────────────────────


class AuthenticationError(LinkedInMCPError):
    """Authentication failed (login required)."""


class CredentialsNotFoundError(AuthenticationError):
    """No credentials available."""


class SessionExpiredError(AuthenticationError):
    """Session has expired and needs refresh."""


# ── Rate Limiting ─────────────────────────────────────────────────────────────


class RateLimitError(LinkedInMCPError):
    """LinkedIn rate limit detected."""

    def __init__(self, message: str, suggested_wait_time: int = 300):
        super().__init__(message)
        self.suggested_wait_time = suggested_wait_time


# ── Scraping ──────────────────────────────────────────────────────────────────


class ScrapingError(LinkedInMCPError):
    """General scraping failure."""


class ElementNotFoundError(ScrapingError):
    """Expected page element not found."""


class ProfileNotFoundError(ScrapingError):
    """Profile/page returned 404."""


# ── Infrastructure ────────────────────────────────────────────────────────────


class NetworkError(LinkedInMCPError):
    """Network-level failure (connection, timeout)."""


class ConfigurationError(LinkedInMCPError):
    """Invalid configuration."""
