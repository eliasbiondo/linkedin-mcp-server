"""Domain models — typed dataclasses representing LinkedIn data."""

from linkedin_mcp_server.domain.models.company import (
    CompanyAbout,
    CompanyJobEntry,
    CompanyJobsSection,
    CompanyPostEntry,
    CompanyPostsSection,
)
from linkedin_mcp_server.domain.models.job import JobPostingDetail
from linkedin_mcp_server.domain.models.person import (
    ContactInfo,
    EducationEntry,
    EducationSection,
    ExperienceEntry,
    ExperienceSection,
    GenericSection,
    PersonMainProfile,
)
from linkedin_mcp_server.domain.models.responses import (
    JobSearchResponse,
    ScrapeResponse,
    SessionStatus,
)
from linkedin_mcp_server.domain.models.search import (
    JobSearchResultEntry,
    JobSearchResults,
    PeopleSearchResults,
    PersonSearchResult,
)

__all__ = [
    "CompanyAbout",
    "CompanyJobEntry",
    "CompanyJobsSection",
    "CompanyPostEntry",
    "CompanyPostsSection",
    "ContactInfo",
    "EducationEntry",
    "EducationSection",
    "ExperienceEntry",
    "ExperienceSection",
    "GenericSection",
    "JobPostingDetail",
    "JobSearchResponse",
    "JobSearchResultEntry",
    "JobSearchResults",
    "PeopleSearchResults",
    "PersonMainProfile",
    "PersonSearchResult",
    "ScrapeResponse",
    "SessionStatus",
]
