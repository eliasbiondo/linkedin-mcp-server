"""Use-case tests: SDUI pages and empty pages are reported, not silently dropped."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import pytest

from linkedin_mcp_server.application import scrape_base
from linkedin_mcp_server.application.scrape_person import ScrapePersonUseCase
from linkedin_mcp_server.application.search_people import SearchPeopleUseCase
from linkedin_mcp_server.domain.parsers import (
    SDUI_EMPTY_SEARCH_MESSAGE,
    SDUI_UNSUPPORTED_MESSAGE,
)
from linkedin_mcp_server.domain.value_objects import PageContent

SDUI_HTML = '<div componentkey="7c1e"><h2 class="_27506df7">Jane Doe</h2></div>'
LEGACY_EXPERIENCE_HTML = """
<li class="pvs-list__paged-list-item">
  <div data-view-name="profile-component-entity">
    <div class="t-bold"><span aria-hidden="true">Engineer</span></div>
  </div>
</li>
"""


class _FakeBrowser:
    """Serves canned HTML per URL suffix (duck-typed BrowserPort)."""

    def __init__(self, pages: dict[str, str]):
        self._pages = pages

    def _html_for(self, url: str) -> str:
        return next((html for suffix, html in self._pages.items() if url.endswith(suffix)), "")

    @asynccontextmanager
    async def exclusive(self) -> AsyncIterator[None]:
        yield

    async def extract_page_html(self, url: str) -> PageContent:
        return PageContent(url=url, html=self._html_for(url))

    async def extract_overlay_html(self, url: str) -> PageContent:
        return PageContent(url=url, html=self._html_for(url))


class _FakeAuth:
    async def ensure_authenticated(self) -> None:
        return None


def _use_case(cls: Any, pages: dict[str, str]) -> Any:
    return cls(_FakeBrowser(pages), _FakeAuth())  # type: ignore[arg-type]


async def test_person_profile_reports_sdui_and_empty_sections(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(scrape_base, "NAV_DELAY", 0)
    uc = _use_case(
        ScrapePersonUseCase,
        {
            "/janedoe/": SDUI_HTML,
            "/details/experience/": LEGACY_EXPERIENCE_HTML,
            "/overlay/contact-info/": "",
        },
    )

    result = await uc.execute("janedoe", "experience,contact_info")

    assert "main_profile" not in result.sections
    assert result.failed_sections["main_profile"] == SDUI_UNSUPPORTED_MESSAGE
    assert result.failed_sections["contact_info"] == "No content extracted from page"
    assert "experience" in result.sections
    assert "experience" not in result.failed_sections


async def test_people_search_reports_unparsed_sdui_results():
    uc = _use_case(SearchPeopleUseCase, {"": SDUI_HTML})

    result = await uc.execute("expert comptable", "Lille")

    assert result.sections == {}
    assert result.failed_sections == {"search_results": SDUI_EMPTY_SEARCH_MESSAGE}


async def test_people_search_keeps_genuinely_empty_legacy_results():
    uc = _use_case(SearchPeopleUseCase, {"": "<div><p>No results found</p></div>"})

    result = await uc.execute("nobody")

    assert result.sections["search_results"].people == []
    assert result.failed_sections == {}
