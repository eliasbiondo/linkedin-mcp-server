"""Browser port — abstracts all browser interaction."""

from abc import ABC, abstractmethod

from linkedin_mcp_server.domain.value_objects import PageContent


class BrowserPort(ABC):
    """Port for browser interaction (page navigation, HTML extraction, scrolling)."""

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
    async def close(self) -> None:
        """Close browser and release resources."""
        ...
