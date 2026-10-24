"""Concurrency tests for the shared-page Patchright browser adapter."""

import asyncio
from typing import Any

from linkedin_mcp_server.adapters.driven.patchright_browser import PatchrightBrowserAdapter
from linkedin_mcp_server.domain.value_objects import BrowserConfig


class _FakeLocator:
    @property
    def first(self) -> "_FakeLocator":
        return self

    async def is_visible(self, timeout: int = 0) -> bool:
        return False


class _FakePage:
    """Minimal stand-in for a Patchright Page.

    ``goto`` and ``evaluate`` yield to the event loop like the real I/O-bound
    calls, so concurrent callers can interleave between navigation and
    extraction unless the adapter serializes them.
    """

    def __init__(self) -> None:
        self.url = "about:blank"

    async def goto(self, url: str, wait_until: str = "load") -> None:
        await asyncio.sleep(0.01)
        self.url = url

    async def evaluate(self, script: str) -> Any:
        await asyncio.sleep(0.01)
        if "innerText" in script:
            return ""
        return f"<p>{self.url}</p>"

    async def wait_for_selector(self, selector: str, timeout: int = 0) -> None:
        await asyncio.sleep(0)

    def locator(self, selector: str) -> _FakeLocator:
        return _FakeLocator()


def _make_adapter() -> tuple[PatchrightBrowserAdapter, _FakePage]:
    adapter = PatchrightBrowserAdapter(BrowserConfig())
    page = _FakePage()
    # Bypass the real browser launch: _ensure_browser() returns the cached page.
    adapter._page = page  # type: ignore[assignment]
    adapter._context = object()  # type: ignore[assignment]
    return adapter, page


async def test_concurrent_extractions_return_their_own_page() -> None:
    adapter, _ = _make_adapter()
    urls = [f"https://www.linkedin.com/in/user{i}/" for i in range(5)]

    results = await asyncio.gather(*(adapter.extract_page_html(url) for url in urls))

    for url, content in zip(urls, results, strict=True):
        assert content.url == url
        assert content.html == f"<p>{url}</p>"


async def test_exclusive_is_reentrant_within_a_task() -> None:
    adapter, _ = _make_adapter()

    async def nested() -> str:
        async with adapter.exclusive(), adapter.exclusive():
            content = await adapter.extract_page_html("https://www.linkedin.com/in/a/")
            return content.url

    assert await asyncio.wait_for(nested(), timeout=2) == "https://www.linkedin.com/in/a/"


async def test_exclusive_blocks_other_tasks_across_multiple_calls() -> None:
    adapter, page = _make_adapter()
    seen: list[str] = []

    async def multi_step() -> None:
        async with adapter.exclusive():
            await adapter.navigate("https://www.linkedin.com/jobs/search/")
            await asyncio.sleep(0.05)  # e.g. NAV_DELAY between dependent steps
            seen.append(await adapter.get_current_url())

    async def intruder() -> None:
        await asyncio.sleep(0.02)  # start while multi_step holds the browser
        await adapter.navigate("https://www.linkedin.com/company/other/")

    await asyncio.gather(multi_step(), intruder())

    assert seen == ["https://www.linkedin.com/jobs/search/"]
    assert page.url == "https://www.linkedin.com/company/other/"
