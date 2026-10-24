"""Browser port — abstracts all browser interaction."""

from abc import ABC, abstractmethod
from contextlib import AbstractAsyncContextManager
from typing import Any

from linkedin_mcp_server.domain.value_objects import PageContent


class BrowserPort(ABC):
    """Port for browser interaction (page navigation, HTML extraction, scrolling).

    Implementations drive a single shared page, so concurrent callers must not
    interleave. Every method is individually serialized; use ``exclusive()`` to
    hold the browser across a multi-step logical operation.
    """

    @abstractmethod
    def exclusive(self) -> AbstractAsyncContextManager[None]:
        """Hold exclusive access to the browser for a multi-step operation.

        Use this when a caller performs several browser calls that depend on
        each other (e.g. navigate, then read state from the loaded page) so no
        concurrent operation can navigate the page in between. Re-entrant
        within the same task: browser methods called while it is held do not
        deadlock.
        """
        ...

    @abstractmethod
    async def navigate(self, url: str, wait_until: str = "domcontentloaded") -> None:
        """Navigate to a URL."""
        ...

    @abstractmethod
    async def extract_page_html(self, url: str) -> PageContent:
        """Navigate to URL, scroll to load content, extract main element innerHTML.

        Returns PageContent with the HTML of the <main> element (or body fallback).
        Handles rate-limit detection and retry internally.
        """
        ...

    @abstractmethod
    async def extract_overlay_html(self, url: str) -> PageContent:
        """Navigate to URL, wait for dialog/modal, extract overlay innerHTML."""
        ...

    @abstractmethod
    async def extract_search_page_html(self, url: str) -> PageContent:
        """Navigate to URL, scroll job sidebar, extract search results HTML."""
        ...

    @abstractmethod
    async def extract_job_ids(self) -> list[str]:
        """Extract job IDs from the currently loaded page."""
        ...

    @abstractmethod
    async def get_total_search_pages(self) -> int | None:
        """Read total page count from LinkedIn pagination state."""
        ...

    @abstractmethod
    async def get_current_url(self) -> str:
        """Return the current page URL."""
        ...

    @abstractmethod
    async def get_cookies(self, urls: list[str] | None = None) -> list[dict[str, Any]]:
        """Return cookies from the browser context.

        Args:
            urls: Optional list of URLs to filter cookies for.
                  If None, returns all cookies.
        """
        ...

    @abstractmethod
    async def add_cookies(self, cookies: list[dict[str, Any]]) -> None:
        """Add cookies to the browser context."""
        ...

    @abstractmethod
    def is_alive(self) -> bool:
        """Check if the browser instance is running and usable."""
        ...

    @abstractmethod
    async def close(self) -> None:
        """Close browser and release resources."""
        ...
