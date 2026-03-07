"""Search for people on LinkedIn."""

from typing import Any
from urllib.parse import quote_plus

from linkedin_mcp_server.domain.models.responses import ScrapeResponse
from linkedin_mcp_server.domain.parsers import parse_section
from linkedin_mcp_server.ports.auth import AuthPort
from linkedin_mcp_server.ports.browser import BrowserPort


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
        if content.html:
            sections["search_results"] = parse_section(
                "search_results",
                content.html,
                entity_type="search_people",
                include_raw=self._debug,
            )

        return ScrapeResponse(url=url, sections=sections)
