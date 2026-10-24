"""Scrape a LinkedIn company profile with configurable sections."""

from linkedin_mcp_server.application.scrape_base import scrape_sections
from linkedin_mcp_server.domain.models.responses import ScrapeResponse
from linkedin_mcp_server.domain.parsers import (
    COMPANY_SECTIONS,
    parse_company_sections,
)
from linkedin_mcp_server.ports.auth import AuthPort
from linkedin_mcp_server.ports.browser import BrowserPort


class ScrapeCompanyUseCase:
    """Scrape a LinkedIn company profile with configurable sections."""

    def __init__(self, browser: BrowserPort, auth: AuthPort, *, debug: bool = False):
        self._browser = browser
        self._auth = auth
        self._debug = debug

    async def execute(
        self,
        company_name: str,
        sections: str | None = None,
    ) -> ScrapeResponse:
        requested, unknown = parse_company_sections(sections)
        requested = set(COMPANY_SECTIONS.keys()) if not requested else requested | {"about"}

        # Hold the browser for the whole profile (auth check + every section)
        # so concurrent tool calls cannot interleave navigations on the shared
        # page, and the inter-section delay keeps pacing requests as intended.
        async with self._browser.exclusive():
            return await scrape_sections(
                browser=self._browser,
                auth=self._auth,
                debug=self._debug,
                base_url=f"https://www.linkedin.com/company/{company_name}",
                entity_type="company",
                sections_registry=COMPANY_SECTIONS,
                requested=requested,
                unknown=unknown,
                entity_label=company_name,
            )
