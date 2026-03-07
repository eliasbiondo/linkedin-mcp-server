"""Search-related domain models."""

from dataclasses import dataclass, field


@dataclass
class PersonSearchResult:
    """A single person result from people search."""

    name: str
    connection_degree: str
    headline: str | None = None
    location: str | None = None
    current: str | None = None
    mutual_connections: str | None = None
    followers: str | None = None
    profile_url: str | None = None
    linkedin_username: str | None = None
    profile_image_url: str | None = None


@dataclass
class PeopleSearchResults:
    """People search results page."""

    people: list[PersonSearchResult] = field(default_factory=list)
    raw: str | None = None


@dataclass
class JobSearchResultEntry:
    """A single job result from job search."""

    title: str | None = None
    company: str | None = None
    location: str | None = None
    job_id: str | None = None
    job_url: str | None = None
    company_logo_url: str | None = None
    insight: str | None = None
    metadata: str | None = None


@dataclass
class JobSearchResults:
    """Job search results page."""

    total_results: str | None = None
    jobs: list[JobSearchResultEntry] = field(default_factory=list)
    raw: str | None = None
