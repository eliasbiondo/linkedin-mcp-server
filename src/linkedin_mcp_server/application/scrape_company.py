"""Scrape a LinkedIn company profile with configurable sections."""

import asyncio
import logging
from typing import Any

from linkedin_mcp_server.domain.models.responses import ScrapeResponse
from linkedin_mcp_server.domain.parsers import (
    COMPANY_SECTIONS,
    parse_company_sections,
    parse_section,
)
from linkedin_mcp_server.domain.parsers.person import parse_generic
from linkedin_mcp_server.ports.auth import AuthPort
from linkedin_mcp_server.ports.browser import BrowserPort

logger = logging.getLogger(__name__)

_NAV_DELAY = 2.0


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
        await self._auth.ensure_authenticated()

        requested, unknown = parse_company_sections(sections)
        requested = (
            set(COMPANY_SECTIONS.keys())
            if not requested
            else requested | {"about"}
        )

        base_url = f"https://www.linkedin.com/company/{company_name}"
        parsed_sections: dict[str, Any] = {}

        first = True
        for section_name, section_config in COMPANY_SECTIONS.items():
            if section_name not in requested:
                continue

            if not first:
                await asyncio.sleep(_NAV_DELAY)
            first = False

            url = base_url + section_config.url_suffix
            content = await self._browser.extract_page_html(url)

            if content.html:
                try:
                    parsed_sections[section_name] = parse_section(
                        section_name,
                        content.html,
                        entity_type="company",
                        include_raw=self._debug,
                    )
                except NotImplementedError:
                    logger.warning(
                        "Parser not implemented for section '%s', using generic",
                        section_name,
                    )
                    parsed_sections[section_name] = parse_generic(
                        content.html, include_raw=self._debug
                    )

        return ScrapeResponse(
            url=f"{base_url}/",
            sections=parsed_sections,
            unknown_sections=unknown,
        )
