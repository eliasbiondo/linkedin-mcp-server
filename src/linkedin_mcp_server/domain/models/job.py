"""Job-related domain models."""

from dataclasses import dataclass, field


@dataclass
class JobPostingDetail:
    """Job posting detail page — extracted from /jobs/view/{job_id}/."""

    title: str | None = None
    company: str | None = None
    company_url: str | None = None
    company_logo_url: str | None = None
    location: str | None = None
    posted_time: str | None = None
    applicant_info: str | None = None
    work_type: list[str] = field(default_factory=list)
    description: str | None = None
    job_id: str | None = None
    raw: str | None = None
