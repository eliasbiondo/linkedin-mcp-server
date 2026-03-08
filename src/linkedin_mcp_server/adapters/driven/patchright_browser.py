"""Patchright browser adapter — BrowserPort implementation.

Handles browser lifecycle, page navigation, scrolling, modal dismissal,
rate limit detection, and HTML extraction.
"""

import asyncio
import logging
import random
from pathlib import Path

from patchright.async_api import (
    Browser,
    BrowserContext,
    Page,
    Playwright,
    async_playwright,
)

from linkedin_mcp_server.domain.exceptions import (
    NetworkError,
    RateLimitError,
)
from linkedin_mcp_server.domain.value_objects import BrowserConfig, PageContent
from linkedin_mcp_server.ports.browser import BrowserPort

logger = logging.getLogger(__name__)

_RATE_LIMIT_MARKERS = [
    "we've detected unusual activity",
    "you've reached the limit",
    "too many requests",
]

# Realistic Chrome user agents — one is picked randomly per session
# when no custom user_agent is configured.
_UA_CHROME = "AppleWebKit/537.36 (KHTML, like Gecko)"
_USER_AGENT_POOL = [
    f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) {_UA_CHROME} Chrome/131.0.0.0 Safari/537.36",
    f"Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) {_UA_CHROME} Chrome/131.0.0.0 Safari/537.36",
    f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) {_UA_CHROME} Chrome/130.0.0.0 Safari/537.36",
    f"Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) {_UA_CHROME} Chrome/130.0.0.0 Safari/537.36",
    f"Mozilla/5.0 (X11; Linux x86_64) {_UA_CHROME} Chrome/131.0.0.0 Safari/537.36",
    f"Mozilla/5.0 (X11; Linux x86_64) {_UA_CHROME} Chrome/130.0.0.0 Safari/537.36",
]


class PatchrightBrowserAdapter(BrowserPort):
    """BrowserPort implementation using Patchright persistent browser."""

    def __init__(self, config: BrowserConfig):
        self._config = config
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None

    async def _ensure_browser(self) -> Page:
        """Lazy-initialize the browser on first use."""
        if self._page is not None:
            return self._page

        self._playwright = await async_playwright().start()

        user_data_dir = str(Path(self._config.user_data_dir).expanduser())

        # Use configured user agent or pick a random realistic one
        user_agent = self._config.user_agent or random.choice(
            _USER_AGENT_POOL
        )
        logger.info("Using user agent: %s", user_agent)

        launch_args: dict = {
            "headless": self._config.headless,
            "slow_mo": self._config.slow_mo,
        }

        if self._config.chrome_path:
            launch_args["executable_path"] = self._config.chrome_path

        self._context = (
            await self._playwright.chromium.launch_persistent_context(
                user_data_dir,
                **launch_args,
                viewport={
                    "width": self._config.viewport_width,
                    "height": self._config.viewport_height,
                },
                user_agent=user_agent,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                ],
            )
        )

        pages = self._context.pages
        self._page = pages[0] if pages else await self._context.new_page()
        self._page.set_default_timeout(self._config.default_timeout)

        logger.info("Browser started with profile: %s", user_data_dir)
        return self._page

    # ── BrowserPort implementation ────────────────────────────────────────────

    async def navigate(self, url: str, wait_until: str = "domcontentloaded") -> None:
        page = await self._ensure_browser()
        last_error: Exception | None = None

        for attempt in range(1, 4):
            try:
                await page.goto(url, wait_until=wait_until)
                return
            except Exception as e:
                last_error = e
                logger.warning(
                    "Navigation attempt %d/3 failed for %s: %s",
                    attempt,
                    url,
                    e,
                )
                if attempt < 3:
                    await asyncio.sleep(attempt * 2)

        raise NetworkError(
            f"Navigation failed after 3 attempts: {url}"
        ) from last_error

    async def extract_page_html(self, url: str) -> PageContent:
        """Navigate, scroll, extract <main> innerHTML."""
        page = await self._ensure_browser()

        try:
            await page.goto(url, wait_until="domcontentloaded")
        except Exception as e:
            logger.error("Page navigation failed for %s: %s", url, e)
            raise NetworkError(f"Navigation failed: {url}") from e

        await self._detect_rate_limit(page)
        await self._handle_modal_close(page)
        await self._wait_for_main(page)
        await self._scroll_to_bottom(page)

        html = await page.evaluate("""
            () => {
                const main = document.querySelector('main');
                return main ? main.innerHTML : document.body.innerHTML;
            }
        """)

        return PageContent(url=page.url, html=html or "")

    async def extract_overlay_html(self, url: str) -> PageContent:
        """Navigate, wait for dialog/modal, extract overlay innerHTML."""
        page = await self._ensure_browser()

        try:
            await page.goto(url, wait_until="domcontentloaded")
        except Exception as e:
            logger.error("Overlay navigation failed for %s: %s", url, e)
            raise NetworkError(f"Navigation failed: {url}") from e

        try:
            await page.wait_for_selector('[role="dialog"]', timeout=5000)
        except Exception:
            logger.warning("Overlay dialog not found for %s", url)

        html = await page.evaluate("""
            () => {
                const dialog = document.querySelector('[role="dialog"]');
                return dialog ? dialog.innerHTML : '';
            }
        """)

        return PageContent(url=page.url, html=html or "")

    async def extract_search_page_html(self, url: str) -> PageContent:
        """Navigate, scroll job sidebar, extract search results HTML."""
        page = await self._ensure_browser()

        try:
            await page.goto(url, wait_until="domcontentloaded")
        except Exception as e:
            logger.error("Search page navigation failed for %s: %s", url, e)
            raise NetworkError(f"Navigation failed: {url}") from e

        await self._detect_rate_limit(page)
        await self._handle_modal_close(page)
        await self._wait_for_main(page)
        await self._scroll_job_sidebar(page)

        html = await page.evaluate("""
            () => {
                const main = document.querySelector('main');
                return main ? main.innerHTML : document.body.innerHTML;
            }
        """)

        return PageContent(url=page.url, html=html or "")

    async def extract_job_ids(self) -> list[str]:
        """Extract job IDs from the currently loaded job search page."""
        page = await self._ensure_browser()

        try:
            return await page.evaluate("""
                () => {
                    const cards = document.querySelectorAll(
                        '[data-job-id], [data-occludable-job-id]'
                    );
                    const ids = new Set();
                    for (const card of cards) {
                        const jid = card.getAttribute('data-job-id')
                            || card.getAttribute('data-occludable-job-id')
                            || '';
                        const cleaned = jid.trim();
                        if (cleaned && /^\\d+$/.test(cleaned)) {
                            ids.add(cleaned);
                        }
                    }
                    return [...ids];
                }
            """)
        except Exception as e:
            logger.warning("Failed to extract job IDs: %s", e)
            return []

    async def get_total_search_pages(self) -> int | None:
        """Read total page count from LinkedIn pagination."""
        page = await self._ensure_browser()

        try:
            return await page.evaluate("""
                () => {
                    const pageState = document.querySelector(
                        '[data-test-pagination-page-btn]:last-of-type'
                    );
                    if (pageState) {
                        const text = pageState.textContent.trim();
                        const num = parseInt(text, 10);
                        return isNaN(num) ? null : num;
                    }
                    return null;
                }
            """)
        except Exception:
            return None

    async def get_current_url(self) -> str:
        page = await self._ensure_browser()
        return page.url

    async def close(self) -> None:
        """Close browser and release resources."""
        if self._context:
            try:
                await self._context.close()
            except Exception as e:
                logger.warning("Error closing browser context: %s", e)
            self._context = None
            self._page = None

        if self._playwright:
            try:
                await self._playwright.stop()
            except Exception as e:
                logger.warning("Error stopping playwright: %s", e)
            self._playwright = None

        logger.info("Browser closed")

    # ── Internal helpers ──────────────────────────────────────────────────────

    async def _detect_rate_limit(self, page: Page) -> None:
        """Check if LinkedIn is rate-limiting and raise if so."""
        try:
            body_text = await page.evaluate("() => document.body.innerText.toLowerCase()")
            for marker in _RATE_LIMIT_MARKERS:
                if marker in body_text:
                    raise RateLimitError(
                        f"Rate limit detected on {page.url}",
                        suggested_wait_time=300,
                    )
        except RateLimitError:
            raise
        except Exception:
            pass  # Don't fail hard on detection errors

    async def _handle_modal_close(self, page: Page) -> None:
        """Dismiss any modal overlays (cookie consent, etc.)."""
        try:
            dismiss_btn = page.locator(
                'button:has-text("Dismiss"), '
                'button[aria-label="Dismiss"], '
                'button:has-text("Got it"), '
                'button:has-text("Accept")'
            ).first
            if await dismiss_btn.is_visible(timeout=1000):
                await dismiss_btn.click()
                await asyncio.sleep(0.5)
        except Exception:
            pass  # Modal dismissal is best-effort

    async def _wait_for_main(self, page: Page) -> None:
        """Wait for the <main> element to appear."""
        try:
            await page.wait_for_selector("main", timeout=self._config.default_timeout)
        except Exception:
            logger.warning("Main element not found on %s", page.url)

    async def _scroll_to_bottom(self, page: Page) -> None:
        """Scroll page to load lazy content."""
        try:
            await page.evaluate("""
                async () => {
                    const delay = ms => new Promise(r => setTimeout(r, ms));
                    const height = () => document.body.scrollHeight;
                    let prev = 0;
                    while (height() !== prev) {
                        prev = height();
                        window.scrollTo(0, prev);
                        await delay(800);
                    }
                }
            """)
        except Exception as e:
            logger.debug("Scroll error (non-fatal): %s", e)

    async def _scroll_job_sidebar(self, page: Page) -> None:
        """Scroll the job sidebar to load all job cards."""
        try:
            await page.evaluate("""
                async () => {
                    const delay = ms => new Promise(r => setTimeout(r, ms));
                    const sidebar = document.querySelector(
                        '.jobs-search-results-list, [class*="jobs-search"]'
                    );
                    if (!sidebar) return;
                    let prev = 0;
                    for (let i = 0; i < 20; i++) {
                        sidebar.scrollTop = sidebar.scrollHeight;
                        await delay(600);
                        if (sidebar.scrollTop === prev) break;
                        prev = sidebar.scrollTop;
                    }
                }
            """)
        except Exception as e:
            logger.debug("Job sidebar scroll error (non-fatal): %s", e)
