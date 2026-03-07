"""Response models — top-level containers returned by use cases."""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ScrapeResponse:
    """Generic scrape response with URL and typed section data."""

    url: str
    sections: dict[str, Any] = field(default_factory=dict)
    unknown_sections: list[str] = field(default_factory=list)


@dataclass
class JobSearchResponse:
    """Job search response with extracted job IDs."""

    url: str
    sections: dict[str, Any] = field(default_factory=dict)
    job_ids: list[str] = field(default_factory=list)


@dataclass
class SessionStatus:
    """Represents the status of a browser session."""

    is_valid: bool
    profile_path: str | None = None
    message: str = ""
