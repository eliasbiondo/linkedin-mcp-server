"""Scrape a single LinkedIn job posting."""

from typing import Any

from linkedin_mcp_server.domain.models.responses import ScrapeResponse
from linkedin_mcp_server.domain.parsers import parse_section
from linkedin_mcp_server.ports.auth import AuthPort
from linkedin_mcp_server.ports.browser import BrowserPort


class ScrapeJobUseCase:
    """Scrape a single LinkedIn job posting by ID."""

    def __init__(self, browser: BrowserPort, auth: AuthPort, *, debug: bool = False):
        self._browser = browser
        self._auth = auth
        self._debug = debug

    async def execute(self, job_id: str) -> ScrapeResponse:
        await self._auth.ensure_authenticated()

        url = f"https://www.linkedin.com/jobs/view/{job_id}/"
        content = await self._browser.extract_page_html(url)

        sections: dict[str, Any] = {}
        if content.html:
            sections["job_posting"] = parse_section(
                "job_posting",
                content.html,
                entity_type="job",
                include_raw=self._debug,
            )

        return ScrapeResponse(url=url, sections=sections)
