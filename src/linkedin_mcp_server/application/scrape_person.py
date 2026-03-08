"""Scrape a LinkedIn person profile with configurable sections."""

import asyncio
import logging
from typing import Any

from linkedin_mcp_server.domain.exceptions import (
    AuthenticationError,
    RateLimitError,
)
from linkedin_mcp_server.domain.models.responses import ScrapeResponse
from linkedin_mcp_server.domain.parsers import (
    PERSON_SECTIONS,
    parse_person_sections,
    parse_section,
)
from linkedin_mcp_server.domain.parsers.person import parse_generic
from linkedin_mcp_server.ports.auth import AuthPort
from linkedin_mcp_server.ports.browser import BrowserPort

logger = logging.getLogger(__name__)

_NAV_DELAY = 2.0


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
        await self._auth.ensure_authenticated()

        requested, unknown = parse_person_sections(sections)
        requested = (
            set(PERSON_SECTIONS.keys())
            if not requested
            else {"main_profile"} | requested
        )

        base_url = f"https://www.linkedin.com/in/{username}"
        parsed_sections: dict[str, Any] = {}
        failed_sections: dict[str, str] = {}

        first = True
        for section_name, section_config in PERSON_SECTIONS.items():
            if section_name not in requested:
                continue

            if not first:
                await asyncio.sleep(_NAV_DELAY)
            first = False

            url = base_url + section_config.url_suffix

            try:
                if section_config.is_overlay:
                    content = await self._browser.extract_overlay_html(url)
                else:
                    content = await self._browser.extract_page_html(url)
            except (RateLimitError, AuthenticationError):
                raise
            except Exception as e:
                logger.warning(
                    "Failed to scrape section '%s' for %s: %s",
                    section_name,
                    username,
                    e,
                )
                failed_sections[section_name] = str(e)
                continue

            if content.html:
                try:
                    try:
                        parsed_sections[section_name] = parse_section(
                            section_name,
                            content.html,
                            entity_type="person",
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
                except Exception as e:
                    logger.warning(
                        "Failed to parse section '%s' for %s: %s",
                        section_name,
                        username,
                        e,
                    )
                    failed_sections[section_name] = f"Parse error: {e}"

        return ScrapeResponse(
            url=f"{base_url}/",
            sections=parsed_sections,
            unknown_sections=unknown,
            failed_sections=failed_sections,
        )
