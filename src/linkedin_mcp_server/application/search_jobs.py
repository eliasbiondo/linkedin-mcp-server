"""Search for jobs on LinkedIn with pagination and filters."""

import asyncio
import logging
from typing import Any
from urllib.parse import quote_plus

from linkedin_mcp_server.domain.models.responses import JobSearchResponse
from linkedin_mcp_server.domain.parsers import parse_section
from linkedin_mcp_server.ports.auth import AuthPort
from linkedin_mcp_server.ports.browser import BrowserPort

logger = logging.getLogger(__name__)

_NAV_DELAY = 2.0

# LinkedIn URL parameter mappings
_DATE_POSTED_MAP = {
    "past_hour": "r3600",
    "past_24_hours": "r86400",
    "past_week": "r604800",
    "past_month": "r2592000",
}

_JOB_TYPE_MAP = {
    "full_time": "F",
    "part_time": "P",
    "contract": "C",
    "temporary": "T",
    "volunteer": "V",
    "internship": "I",
    "other": "O",
}

_EXPERIENCE_LEVEL_MAP = {
    "internship": "1",
    "entry": "2",
    "associate": "3",
    "mid_senior": "4",
    "director": "5",
    "executive": "6",
}

_WORK_TYPE_MAP = {
    "on_site": "1",
    "remote": "2",
    "hybrid": "3",
}

_SORT_MAP = {
    "date": "DD",
    "relevance": "R",
}


class SearchJobsUseCase:
    """Search for jobs on LinkedIn with pagination and filters."""

    def __init__(self, browser: BrowserPort, auth: AuthPort, *, debug: bool = False):
        self._browser = browser
        self._auth = auth
        self._debug = debug

    async def execute(
        self,
        keywords: str,
        location: str | None = None,
        max_pages: int = 3,
        date_posted: str | None = None,
        job_type: str | None = None,
        experience_level: str | None = None,
        work_type: str | None = None,
        easy_apply: bool = False,
        sort_by: str | None = None,
    ) -> JobSearchResponse:
        await self._auth.ensure_authenticated()

        base_url = self._build_search_url(
            keywords=keywords,
            location=location,
            date_posted=date_posted,
            job_type=job_type,
            experience_level=experience_level,
            work_type=work_type,
            easy_apply=easy_apply,
            sort_by=sort_by,
        )

        all_job_ids: list[str] = []
        seen_ids: set[str] = set()
        sections: dict[str, Any] = {}

        max_pages = max(1, min(max_pages, 10))

        for page_num in range(max_pages):
            page_url = base_url if page_num == 0 else f"{base_url}&start={page_num * 25}"

            if page_num > 0:
                await asyncio.sleep(_NAV_DELAY)

            content = await self._browser.extract_search_page_html(page_url)

            # Extract job IDs from the loaded page
            page_job_ids = await self._browser.extract_job_ids()
            for jid in page_job_ids:
                if jid not in seen_ids:
                    seen_ids.add(jid)
                    all_job_ids.append(jid)

            if content.html:
                parsed = parse_section(
                    "search_results",
                    content.html,
                    entity_type="search_jobs",
                    include_raw=self._debug,
                )
                sections[f"page_{page_num + 1}"] = parsed

            # Check if there are more pages
            if page_num == 0:
                total_pages = await self._browser.get_total_search_pages()
                if total_pages is not None:
                    max_pages = min(max_pages, total_pages)

        return JobSearchResponse(
            url=base_url,
            sections=sections,
            job_ids=all_job_ids,
        )

    @staticmethod
    def _build_search_url(
        *,
        keywords: str,
        location: str | None = None,
        date_posted: str | None = None,
        job_type: str | None = None,
        experience_level: str | None = None,
        work_type: str | None = None,
        easy_apply: bool = False,
        sort_by: str | None = None,
    ) -> str:
        """Build LinkedIn job search URL with filters."""
        params = [f"keywords={quote_plus(keywords)}"]

        if location:
            params.append(f"location={quote_plus(location)}")

        if date_posted and date_posted in _DATE_POSTED_MAP:
            params.append(f"f_TPR={_DATE_POSTED_MAP[date_posted]}")

        if job_type:
            codes = _map_comma_separated(job_type, _JOB_TYPE_MAP)
            if codes:
                params.append(f"f_JT={codes}")

        if experience_level:
            codes = _map_comma_separated(experience_level, _EXPERIENCE_LEVEL_MAP)
            if codes:
                params.append(f"f_E={codes}")

        if work_type:
            codes = _map_comma_separated(work_type, _WORK_TYPE_MAP)
            if codes:
                params.append(f"f_WT={codes}")

        if easy_apply:
            params.append("f_AL=true")

        if sort_by and sort_by in _SORT_MAP:
            params.append(f"sortBy={_SORT_MAP[sort_by]}")

        return f"https://www.linkedin.com/jobs/search/?{'&'.join(params)}"


def _map_comma_separated(value: str, mapping: dict[str, str]) -> str:
    """Map comma-separated user-friendly names to LinkedIn URL codes."""
    codes = []
    for item in value.split(","):
        item = item.strip()
        if item in mapping:
            codes.append(mapping[item])
        else:
            logger.warning("Unknown filter value: %s", item)
    return "%2C".join(codes)
