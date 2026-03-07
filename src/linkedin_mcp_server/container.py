"""Dependency Injection container — the composition root.

This is the single place where ports are wired to adapter implementations
and use cases are assembled. Only this file imports concrete adapter classes.
"""

from linkedin_mcp_server.adapters.driven.patchright_browser import PatchrightBrowserAdapter
from linkedin_mcp_server.adapters.driven.profile_auth import ProfileAuthAdapter
from linkedin_mcp_server.application.manage_session import ManageSessionUseCase
from linkedin_mcp_server.application.scrape_company import ScrapeCompanyUseCase
from linkedin_mcp_server.application.scrape_job import ScrapeJobUseCase
from linkedin_mcp_server.application.scrape_person import ScrapePersonUseCase
from linkedin_mcp_server.application.search_jobs import SearchJobsUseCase
from linkedin_mcp_server.application.search_people import SearchPeopleUseCase
from linkedin_mcp_server.domain.value_objects import AppConfig
from linkedin_mcp_server.ports.auth import AuthPort
from linkedin_mcp_server.ports.browser import BrowserPort


class Container:
    """Dependency Injection container.

    Wires ports to adapters and creates use case instances.
    This is the only place in the codebase where concrete adapter
    classes are imported and instantiated.
    """

    def __init__(self, config: AppConfig):
        self._config = config
        debug = config.server.log_level == "DEBUG"

        self._browser: BrowserPort = PatchrightBrowserAdapter(config.browser)
        self._auth: AuthPort = ProfileAuthAdapter(self._browser, config.browser)

        self._scrape_person = ScrapePersonUseCase(self._browser, self._auth, debug=debug)
        self._scrape_company = ScrapeCompanyUseCase(self._browser, self._auth, debug=debug)
        self._scrape_job = ScrapeJobUseCase(self._browser, self._auth, debug=debug)
        self._search_people = SearchPeopleUseCase(self._browser, self._auth, debug=debug)
        self._search_jobs = SearchJobsUseCase(self._browser, self._auth, debug=debug)
        self._manage_session = ManageSessionUseCase(self._browser, self._auth)

    @property
    def config(self) -> AppConfig:
        return self._config

    @property
    def browser(self) -> BrowserPort:
        return self._browser

    @property
    def auth(self) -> AuthPort:
        return self._auth

    @property
    def scrape_person(self) -> ScrapePersonUseCase:
        return self._scrape_person

    @property
    def scrape_company(self) -> ScrapeCompanyUseCase:
        return self._scrape_company

    @property
    def scrape_job(self) -> ScrapeJobUseCase:
        return self._scrape_job

    @property
    def search_people(self) -> SearchPeopleUseCase:
        return self._search_people

    @property
    def search_jobs(self) -> SearchJobsUseCase:
        return self._search_jobs

    @property
    def manage_session(self) -> ManageSessionUseCase:
        return self._manage_session
