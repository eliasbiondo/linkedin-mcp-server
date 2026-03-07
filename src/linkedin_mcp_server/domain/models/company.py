"""Company-related domain models."""

from dataclasses import dataclass, field


@dataclass
class CompanyAbout:
    """Company about/overview page — extracted from /company/{name}/about/."""

    name: str | None = None
    overview: str | None = None
    website: str | None = None
    phone: str | None = None
    industry: str | None = None
    company_size: str | None = None
    headquarters: str | None = None
    type: str | None = None
    founded: str | None = None
    specialties: str | None = None
    followers: str | None = None
    employees_on_linkedin: str | None = None
    logo_url: str | None = None
    raw: str | None = None


@dataclass
class CompanyJobEntry:
    """A single job listing from a company's jobs page."""

    title: str | None = None
    job_id: str | None = None
    job_url: str | None = None
    company: str | None = None
    location: str | None = None
    posted_time: str | None = None
    metadata: str | None = None


@dataclass
class CompanyJobsSection:
    """Company jobs page — extracted from /company/{name}/jobs/."""

    total_openings: str | None = None
    jobs: list[CompanyJobEntry] = field(default_factory=list)
    raw: str | None = None


@dataclass
class CompanyPostEntry:
    """A single post from a company's feed."""

    text: str | None = None
    time_posted: str | None = None
    reactions: str | None = None
    comments: str | None = None
    reposts: str | None = None


@dataclass
class CompanyPostsSection:
    """Company posts feed — extracted from /company/{name}/posts/."""

    posts: list[CompanyPostEntry] = field(default_factory=list)
    raw: str | None = None
