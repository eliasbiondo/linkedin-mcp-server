"""Search for people on LinkedIn."""

import logging
from typing import Any
from urllib.parse import quote_plus

from linkedin_mcp_server.domain.models.responses import ScrapeResponse
from linkedin_mcp_server.domain.parsers import (
    SDUI_EMPTY_SEARCH_MESSAGE,
    parse_section,
    unsupported_layout_reason,
)
from linkedin_mcp_server.ports.auth import AuthPort
from linkedin_mcp_server.ports.browser import BrowserPort

logger = logging.getLogger(__name__)


class SearchPeopleUseCase:
    """Search for people on LinkedIn."""

    def __init__(self, browser: BrowserPort, auth: AuthPort, *, debug: bool = False):
        self._browser = browser
        self._auth = auth
        self._debug = debug

    async def execute(
        self,
        keywords: str,
        location: str | None = None,
    ) -> ScrapeResponse:
        await self._auth.ensure_authenticated()

        params = f"keywords={quote_plus(keywords)}"
        if location:
            params += f"&location={quote_plus(location)}"

        url = f"https://www.linkedin.com/search/results/people/?{params}"
        content = await self._browser.extract_page_html(url)

        sections: dict[str, Any] = {}
        failed_sections: dict[str, str] = {}
        if content.html:
            parsed = parse_section(
                "search_results",
                content.html,
                entity_type="search_people",
                include_raw=self._debug,
            )
            reason = unsupported_layout_reason(
                content.html, parsed, message=SDUI_EMPTY_SEARCH_MESSAGE
            )
            if reason:
                logger.warning("Unsupported (SDUI) layout for people search: %s", url)
                failed_sections["search_results"] = reason
            else:
                sections["search_results"] = parsed

        return ScrapeResponse(url=url, sections=sections, failed_sections=failed_sections)
