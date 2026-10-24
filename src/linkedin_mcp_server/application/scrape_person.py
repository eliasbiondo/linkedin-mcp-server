"""Scrape a LinkedIn person profile with configurable sections."""

from linkedin_mcp_server.application.scrape_base import scrape_sections
from linkedin_mcp_server.domain.models.responses import ScrapeResponse
from linkedin_mcp_server.domain.parsers import (
    PERSON_SECTIONS,
    parse_person_sections,
)
from linkedin_mcp_server.ports.auth import AuthPort
from linkedin_mcp_server.ports.browser import BrowserPort


class ScrapePersonUseCase:
    """Scrape a LinkedIn person profile with configurable sections."""

    def __init__(self, browser: BrowserPort, auth: AuthPort, *, debug: bool = False):
        self._browser = browser
        self._auth = auth
        self._debug = debug

    async def execute(
        self,
        username: str,
        sections: str | None = None,
    ) -> ScrapeResponse:
        requested, unknown = parse_person_sections(sections)
        requested = set(PERSON_SECTIONS.keys()) if not requested else {"main_profile"} | requested

        # Hold the browser for the whole profile (auth check + every section)
        # so concurrent tool calls cannot interleave navigations on the shared
        # page, and the inter-section delay keeps pacing requests as intended.
        async with self._browser.exclusive():
            return await scrape_sections(
                browser=self._browser,
                auth=self._auth,
                debug=self._debug,
                base_url=f"https://www.linkedin.com/in/{username}",
                entity_type="person",
                sections_registry=PERSON_SECTIONS,
                requested=requested,
                unknown=unknown,
                entity_label=username,
            )
