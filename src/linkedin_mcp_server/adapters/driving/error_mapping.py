"""Domain exception → MCP ToolError mapping.

This is the ONLY file that imports from fastmcp.exceptions.
All domain errors are translated to user-friendly ToolError messages here.
"""

import logging
from typing import NoReturn

from fastmcp.exceptions import ToolError

from linkedin_mcp_server.domain.exceptions import (
    AuthenticationError,
    ConfigurationError,
    LinkedInMCPError,
    NetworkError,
    ProfileNotFoundError,
    RateLimitError,
    ScrapingError,
)

logger = logging.getLogger(__name__)


def map_domain_error(exception: Exception, context: str = "") -> NoReturn:
    """Map domain exceptions to ToolError for MCP clients.

    Args:
        exception: The caught exception
        context: Optional context string (e.g. tool name)

    Raises:
        ToolError: Always, with a user-friendly message
    """
    prefix = f"[{context}] " if context else ""

    if isinstance(exception, AuthenticationError):
        raise ToolError(
            f"{prefix}Authentication required. "
            "Please run the server with --login to authenticate first."
        ) from exception

    if isinstance(exception, RateLimitError):
        raise ToolError(
            f"{prefix}LinkedIn rate limit detected. "
            f"Please wait ~{exception.suggested_wait_time // 60} minutes before retrying."
        ) from exception

    if isinstance(exception, ProfileNotFoundError):
        raise ToolError(
            f"{prefix}Profile not found. Please check the username or URL."
        ) from exception

    if isinstance(exception, NetworkError):
        raise ToolError(
            f"{prefix}Network error. Please check your connection and try again."
        ) from exception

    if isinstance(exception, ScrapingError):
        raise ToolError(
            f"{prefix}Failed to extract data from the page. "
            "The page structure may have changed."
        ) from exception

    if isinstance(exception, ConfigurationError):
        raise ToolError(
            f"{prefix}Configuration error: {exception}"
        ) from exception

    if isinstance(exception, LinkedInMCPError):
        raise ToolError(f"{prefix}{exception}") from exception

    # Unknown exception — log and re-raise with masked details
    logger.exception("Unexpected error in %s", context or "unknown context")
    raise ToolError(
        f"{prefix}An unexpected error occurred. Check server logs for details."
    ) from exception
