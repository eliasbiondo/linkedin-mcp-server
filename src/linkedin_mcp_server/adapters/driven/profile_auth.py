"""Profile auth adapter — AuthPort implementation using persistent browser profile."""

import asyncio
import contextlib
import json
import logging
import random
import shutil
import time
from pathlib import Path

from linkedin_mcp_server.domain.exceptions import AuthenticationError
from linkedin_mcp_server.domain.value_objects import BrowserConfig
from linkedin_mcp_server.ports.auth import AuthPort
from linkedin_mcp_server.ports.browser import BrowserPort

logger = logging.getLogger(__name__)

_LOGIN_TIMEOUT_S = 300  # 5 minutes to complete login
_LOGIN_POLL_INTERVAL_S = 2  # Check every 2 seconds
_COOKIE_FLUSH_DELAY_S = 3  # Wait for cookies to persist to disk

# How long a successful auth check is considered valid (avoid re-checking)
_AUTH_CACHE_TTL_S = 120  # 2 minutes

# The LinkedIn session cookie we check for
_SESSION_COOKIE_NAME = "li_at"

_AUTH_BLOCKER_PATTERNS = [
    "/login",
    "/authwall",
    "/checkpoint",
    "/challenge",
    "/uas/login",
    "/uas/consumer-email-challenge",
]

_AUTHENTICATED_PAGE_PATTERNS = [
    "/feed",
    "/mynetwork",
    "/messaging",
    "/notifications",
    "/in/",
    "/company/",
    "/jobs/",
]

_WARM_UP_POOL = [
    "https://www.google.com",
    "https://www.bing.com",
    "https://www.reddit.com",
    "https://www.stackoverflow.com",
    "https://www.wikipedia.org",
    "https://www.github.com",
    "https://www.amazon.com",
    "https://www.youtube.com",
    "https://www.nytimes.com",
    "https://www.bbc.com",
    "https://www.medium.com",
    "https://news.ycombinator.com",
    "https://www.cnn.com",
    "https://www.weather.com",
    "https://www.imdb.com",
    "https://www.espn.com",
]

_MIN_WARM_UP_SITES = 5
_MAX_WARM_UP_SITES = 7

_COOKIE_EXPORT_FILE = "cookies.json"


class ProfileAuthAdapter(AuthPort):
    """AuthPort implementation using persistent Patchright browser profile.

    Auth detection strategy (ordered by cost):
    1. Cache — if recently validated, skip all checks
    2. Cookie check — look for `li_at` session cookie (fast, no navigation)
    3. Navigation check — navigate to /feed/ and inspect URL (slow, full check)
    """

    def __init__(self, browser: BrowserPort, config: BrowserConfig):
        self._browser = browser
        self._config = config
        self._last_auth_check: float = 0.0
        self._last_auth_result: bool = False
        self._nav_validated: bool = False

    async def is_authenticated(self) -> bool:
        """Check login status using a layered strategy: cache → cookie → navigation.

        The cookie check is a fast *negative* pre-filter: if the cookie is
        missing we fail immediately without navigation.  A present cookie
        is necessary but not sufficient (it could be expired server-side),
        so we still require at least one navigation-verified check per TTL.
        """
        # Layer 1: Cache — avoid redundant checks within TTL
        now = time.monotonic()
        if (
            self._last_auth_result
            and self._nav_validated
            and (now - self._last_auth_check) < _AUTH_CACHE_TTL_S
        ):
            logger.debug("Auth check skipped — cached result still valid")
            return True

        # Layer 2: Cookie pre-check (fast, no network)
        cookie_ok = await self._check_session_cookie()
        if not cookie_ok:
            logger.debug("Auth failed — session cookie missing or expired")
            self._update_cache(False)
            return False

        # Layer 3: Full navigation check (slow but definitive)
        try:
            nav_ok = await self._check_via_navigation()
            self._update_cache(nav_ok, nav_validated=True)
            return nav_ok
        except Exception as e:
            logger.warning("Auth navigation check failed: %s", e)
            self._update_cache(False)
            return False

    async def ensure_authenticated(self) -> None:
        """Validate session and raise AuthenticationError if expired."""
        if not await self.is_authenticated():
            raise AuthenticationError(
                "LinkedIn session is not authenticated. Run with --login to authenticate."
            )

    def has_credentials(self) -> bool:
        """Check if browser profile directory exists and has content."""
        profile_dir = self.get_profile_path()
        if not profile_dir.is_dir():
            return False
        # Check for meaningful content (at least a few files/dirs)
        try:
            children = list(profile_dir.iterdir())
            return len(children) > 0
        except OSError:
            return False

    async def login_interactive(self, warm_up: bool = True) -> bool:
        """Open non-headless browser for manual LinkedIn login.

        Navigates to LinkedIn login, then polls automatically until the user
        completes authentication (including 2FA, captcha, security challenges).
        No manual confirmation needed — login is detected automatically.

        Returns True if login was successful.
        """
        # Hold the browser for the whole flow: we navigate, then poll the
        # current URL, so no other operation may drive the page meanwhile.
        async with self._browser.exclusive():
            return await self._login_interactive(warm_up=warm_up)

    async def _login_interactive(self, warm_up: bool) -> bool:
        if warm_up:
            print("  Warming up browser...")
            await self._warm_up()

        print("  Navigating to LinkedIn login page...")
        await asyncio.sleep(random.uniform(1.0, 3.0))

        try:
            await self._browser.navigate("https://www.linkedin.com/login")
        except Exception as e:
            logger.error("Failed to navigate to LinkedIn login: %s", e)
            raise AuthenticationError(f"Could not open LinkedIn login page: {e}") from e

        print(
            f"  Waiting for login (up to {_LOGIN_TIMEOUT_S // 60} minutes)...\n"
            "  Complete authentication in the browser window.\n"
            "  Supports 2FA, captcha, and security challenges.\n"
        )

        authenticated = await self._poll_for_login()

        if not authenticated:
            raise AuthenticationError(
                "Login timed out. Please try again and complete the login faster."
            )

        # Wait for cookies to flush to disk
        await asyncio.sleep(_COOKIE_FLUSH_DELAY_S)

        # Invalidate cache so the next check does a fresh validation
        self._invalidate_cache()

        # Verify login actually worked
        verified = await self.is_authenticated()
        if not verified:
            logger.warning("Login appeared successful but post-login verification failed")
            raise AuthenticationError(
                "Login appeared to succeed but session verification failed. Please try again."
            )

        print("  Login detected and verified! Session saved.\n")
        return True

    async def export_cookies(self) -> bool:
        """Export session cookies to a JSON file for portability."""
        try:
            cookies = await self._browser.get_cookies(urls=["https://www.linkedin.com"])
            if not cookies:
                logger.warning("No cookies to export")
                return False

            # Filter to LinkedIn cookies only
            # Handle both "linkedin.com" and ".linkedin.com" domains
            linkedin_cookies = [
                c for c in cookies if (c.get("domain") or "").lstrip(".").endswith("linkedin.com")
            ]

            if not linkedin_cookies:
                logger.warning("No LinkedIn cookies found to export")
                return False

            export_path = self.get_profile_path() / _COOKIE_EXPORT_FILE
            export_path.parent.mkdir(parents=True, exist_ok=True)
            export_path.write_text(
                json.dumps(linkedin_cookies, indent=2, default=str),
                encoding="utf-8",
            )
            # Restrict file permissions — cookies are sensitive auth material
            export_path.chmod(0o600)
            logger.info("Exported %d cookies to %s", len(linkedin_cookies), export_path)
            return True
        except Exception as e:
            logger.error("Cookie export failed: %s", e)
            return False

    async def import_cookies(self) -> bool:
        """Import session cookies from a previously exported JSON file."""
        import_path = self.get_profile_path() / _COOKIE_EXPORT_FILE
        if not import_path.exists():
            logger.warning("No cookie file found at %s", import_path)
            return False

        try:
            raw = import_path.read_text(encoding="utf-8")
            cookies = json.loads(raw)

            if not isinstance(cookies, list) or not cookies:
                logger.warning("Cookie file is empty or malformed")
                return False

            # Sanitize cookies for Playwright
            sanitized = self._sanitize_cookies_for_import(cookies)

            await self._browser.add_cookies(sanitized)
            logger.info("Imported %d cookies from %s", len(sanitized), import_path)

            # Invalidate cache to force re-check
            self._invalidate_cache()
            return True
        except json.JSONDecodeError as e:
            logger.error("Cookie file is not valid JSON: %s", e)
            return False
        except Exception as e:
            logger.error("Cookie import failed: %s", e)
            return False

    def clear_credentials(self) -> bool:
        """Clear stored credentials by removing profile directory."""
        profile_dir = self.get_profile_path()
        if profile_dir.exists():
            try:
                shutil.rmtree(profile_dir)
                logger.info("Cleared credentials at %s", profile_dir)
                self._invalidate_cache()
                return True
            except Exception as e:
                logger.error("Failed to clear credentials: %s", e)
                return False
        return True

    def get_profile_path(self) -> Path:
        """Return the path to the browser profile directory."""
        return Path(self._config.user_data_dir).expanduser()

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _update_cache(self, result: bool, *, nav_validated: bool = False) -> None:
        """Update the auth check cache."""
        self._last_auth_check = time.monotonic()
        self._last_auth_result = result
        if nav_validated:
            self._nav_validated = True
        if not result:
            self._nav_validated = False

    def _invalidate_cache(self) -> None:
        """Force the next auth check to do a full validation."""
        self._last_auth_check = 0.0
        self._last_auth_result = False
        self._nav_validated = False

    async def _check_session_cookie(self) -> bool:
        """Check if the `li_at` session cookie exists.

        This is a fast check that doesn't require network navigation.
        It's a necessary but not sufficient condition for auth —
        the cookie might exist but be expired server-side.
        """
        try:
            cookies = await self._browser.get_cookies(urls=["https://www.linkedin.com"])
            for cookie in cookies:
                if cookie.get("name") == _SESSION_COOKIE_NAME:
                    value = cookie.get("value", "")
                    if value and len(value) > 10:
                        # Check expiry if available
                        expires = cookie.get("expires", -1)
                        if expires > 0 and expires < time.time():
                            logger.debug("Session cookie expired")
                            return False
                        return True
            return False
        except Exception as e:
            logger.debug("Cookie check failed (browser may not be initialized): %s", e)
            return False

    async def _check_via_navigation(self) -> bool:
        """Navigate to LinkedIn feed and check if we land on an authenticated page."""
        try:
            # Navigate and read the resulting URL atomically, so a concurrent
            # navigation cannot change the page between the two steps.
            async with self._browser.exclusive():
                await self._browser.navigate("https://www.linkedin.com/feed/")
                url = await self._browser.get_current_url()

            # Fail-fast on auth blocker URLs
            if any(pattern in url for pattern in _AUTH_BLOCKER_PATTERNS):
                return False

            # Authenticated pages confirm login
            return any(pattern in url for pattern in _AUTHENTICATED_PAGE_PATTERNS)
        except Exception as e:
            logger.warning("Auth navigation check failed: %s", e)
            return False

    async def _warm_up(self) -> None:
        """Visit random popular sites to build a natural browsing fingerprint."""
        count = random.randint(_MIN_WARM_UP_SITES, _MAX_WARM_UP_SITES)
        sites = random.sample(_WARM_UP_POOL, min(count, len(_WARM_UP_POOL)))

        for i, site in enumerate(sites, 1):
            logger.info("Warm-up %d/%d: visiting %s", i, len(sites), site)
            print(f"  Warm-up {i}/{len(sites)}: visiting {site}")
            with contextlib.suppress(Exception):
                await self._browser.navigate(site)
                await asyncio.sleep(random.uniform(1.0, 3.0))

        logger.info("Warm-up complete (%d sites visited)", len(sites))

    async def _poll_for_login(self) -> bool:
        """Poll the current URL until login is detected or timeout expires.

        Uses monotonic clock for accurate timeout tracking regardless of
        system clock changes or sleep drift.
        """
        deadline = time.monotonic() + _LOGIN_TIMEOUT_S

        while time.monotonic() < deadline:
            url = await self._browser.get_current_url()

            # Check if we're on an authenticated page
            if any(pattern in url for pattern in _AUTHENTICATED_PAGE_PATTERNS):
                return True

            # Not on a blocker page but also not on a known auth page?
            # Could be transitioning — keep waiting
            await asyncio.sleep(_LOGIN_POLL_INTERVAL_S)

        return False

    @staticmethod
    def _sanitize_cookies_for_import(cookies: list[dict]) -> list[dict]:
        """Sanitize cookies for Playwright's add_cookies() method.

        Playwright requires certain fields and rejects others.
        This ensures compatibility.
        """
        sanitized = []
        for cookie in cookies:
            clean = {
                "name": cookie["name"],
                "value": cookie["value"],
                "domain": cookie.get("domain", ".linkedin.com"),
                "path": cookie.get("path", "/"),
            }
            # Only include valid expiry timestamps
            if "expires" in cookie and cookie["expires"] > 0:
                clean["expires"] = cookie["expires"]

            if "httpOnly" in cookie:
                clean["httpOnly"] = cookie["httpOnly"]
            if "secure" in cookie:
                clean["secure"] = cookie["secure"]
            if "sameSite" in cookie:
                clean["sameSite"] = cookie["sameSite"]

            sanitized.append(clean)
        return sanitized
