"""Base scrape use case — shared logic for multi-section profile scraping."""

import asyncio
import logging
from typing import Any

from linkedin_mcp_server.domain.exceptions import (
    AuthenticationError,
    NetworkError,
    RateLimitError,
)
from linkedin_mcp_server.domain.models.responses import ScrapeResponse
from linkedin_mcp_server.domain.parsers import parse_section, unsupported_layout_reason
from linkedin_mcp_server.domain.parsers.person import parse_generic
from linkedin_mcp_server.domain.value_objects import SectionConfig
from linkedin_mcp_server.ports.auth import AuthPort
from linkedin_mcp_server.ports.browser import BrowserPort

logger = logging.getLogger(__name__)

NAV_DELAY = 2.0


async def scrape_sections(
    *,
    browser: BrowserPort,
    auth: AuthPort,
    debug: bool,
    base_url: str,
    entity_type: str,
    sections_registry: dict[str, SectionConfig],
    requested: set[str],
    unknown: list[str] | None = None,
    entity_label: str = "",
) -> ScrapeResponse:
    """Iterate over requested sections, navigate, extract HTML, and parse.

    This is the shared implementation behind ScrapePersonUseCase and
    ScrapeCompanyUseCase.  Both use-cases follow exactly the same pattern:

    1. Authenticate
    2. Iterate over the section registry, skipping unrequested sections
    3. Navigate to each section URL (with inter-page delay)
    4. Extract HTML (page or overlay)
    5. Parse the HTML with the appropriate registered parser (or fallback)
    6. Accumulate results, tracking any sections that failed (including
       sections whose page came back empty or in an unsupported layout)

    Args:
        browser: BrowserPort implementation
        auth: AuthPort implementation
        debug: Whether to include raw HTML in parsed models
        base_url: Profile base URL (e.g. "https://www.linkedin.com/in/johndoe")
        entity_type: Parser entity type ("person" or "company")
        sections_registry: Ordered dict of section name → SectionConfig
        requested: Set of section names to scrape
        unknown: List of unknown section names from user input
        entity_label: Human label for log messages (e.g. username or company name)
    """
    await auth.ensure_authenticated()

    parsed_sections: dict[str, Any] = {}
    failed_sections: dict[str, str] = {}

    first = True
    for section_name, section_config in sections_registry.items():
        if section_name not in requested:
            continue

        if not first:
            await asyncio.sleep(NAV_DELAY)
        first = False

        url = base_url + section_config.url_suffix

        try:
            if section_config.is_overlay:
                content = await browser.extract_overlay_html(url)
            else:
                content = await browser.extract_page_html(url)
        except (RateLimitError, AuthenticationError, NetworkError):
            raise
        except Exception as e:
            logger.warning(
                "Failed to scrape section '%s' for %s: %s",
                section_name,
                entity_label,
                e,
            )
            failed_sections[section_name] = str(e)
            continue

        if not content.html:
            logger.warning(
                "No content extracted for section '%s' for %s",
                section_name,
                entity_label,
            )
            failed_sections[section_name] = "No content extracted from page"
            continue

        try:
            try:
                parsed = parse_section(
                    section_name,
                    content.html,
                    entity_type=entity_type,
                    include_raw=debug,
                )
            except NotImplementedError:
                logger.warning(
                    "Parser not implemented for section '%s', using generic",
                    section_name,
                )
                parsed = parse_generic(content.html, include_raw=debug)
        except Exception as e:
            logger.warning(
                "Failed to parse section '%s' for %s: %s",
                section_name,
                entity_label,
                e,
            )
            failed_sections[section_name] = f"Parse error: {e}"
            continue

        reason = unsupported_layout_reason(content.html, parsed)
        if reason:
            logger.warning(
                "Unsupported (SDUI) layout for section '%s' for %s",
                section_name,
                entity_label,
            )
            failed_sections[section_name] = reason
            continue

        parsed_sections[section_name] = parsed

    return ScrapeResponse(
        url=f"{base_url}/",
        sections=parsed_sections,
        unknown_sections=unknown or [],
        failed_sections=failed_sections,
    )
