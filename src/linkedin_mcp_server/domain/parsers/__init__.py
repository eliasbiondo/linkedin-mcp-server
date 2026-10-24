"""Domain parsers — pure functions converting HTML to typed models.

Section registries and routing live here.
"""

from dataclasses import fields
from typing import Any

from linkedin_mcp_server.domain.models.company import (
    CompanyAbout,
    CompanyJobsSection,
    CompanyPostsSection,
)
from linkedin_mcp_server.domain.models.job import JobPostingDetail
from linkedin_mcp_server.domain.models.person import (
    ContactInfo,
    EducationSection,
    ExperienceSection,
    GenericSection,
    HonorsSection,
    InterestsSection,
    LanguagesSection,
    PersonMainProfile,
    PersonPostsSection,
    RecommendationsSection,
)
from linkedin_mcp_server.domain.models.search import (
    JobSearchResults,
    PeopleSearchResults,
)
from linkedin_mcp_server.domain.parsers.common import is_sdui_markup
from linkedin_mcp_server.domain.parsers.company import (
    parse_company_about,
    parse_company_jobs,
    parse_company_posts,
)
from linkedin_mcp_server.domain.parsers.job import parse_job_posting
from linkedin_mcp_server.domain.parsers.person import (
    parse_contact_info,
    parse_education,
    parse_experience,
    parse_generic,
    parse_honors,
    parse_interests,
    parse_languages,
    parse_person_main_profile,
    parse_person_posts,
    parse_recommendations,
)
from linkedin_mcp_server.domain.parsers.search import (
    parse_search_results_jobs,
    parse_search_results_people,
)
from linkedin_mcp_server.domain.value_objects import SectionConfig

# ── Section registries ────────────────────────────────────────────────────────

PERSON_SECTIONS: dict[str, SectionConfig] = {
    "main_profile": SectionConfig("main_profile", "/", is_overlay=False),
    "experience": SectionConfig("experience", "/details/experience/"),
    "education": SectionConfig("education", "/details/education/"),
    "interests": SectionConfig("interests", "/details/interests/"),
    "honors": SectionConfig("honors", "/details/honors/"),
    "languages": SectionConfig("languages", "/details/languages/"),
    "contact_info": SectionConfig("contact_info", "/overlay/contact-info/", is_overlay=True),
    "posts": SectionConfig("posts", "/recent-activity/all/"),
    "recommendations": SectionConfig("recommendations", "/details/recommendations/"),
}

COMPANY_SECTIONS: dict[str, SectionConfig] = {
    "about": SectionConfig("about", "/about/"),
    "posts": SectionConfig("posts", "/posts/"),
    "jobs": SectionConfig("jobs", "/jobs/"),
}

# ── Parser type union ─────────────────────────────────────────────────────────

type ParsedSection = (
    PersonMainProfile
    | ExperienceSection
    | EducationSection
    | InterestsSection
    | HonorsSection
    | LanguagesSection
    | PersonPostsSection
    | RecommendationsSection
    | ContactInfo
    | CompanyAbout
    | CompanyPostsSection
    | CompanyJobsSection
    | JobPostingDetail
    | PeopleSearchResults
    | JobSearchResults
    | GenericSection
)

# ── Parser registries ─────────────────────────────────────────────────────────

_PERSON_PARSERS: dict[str, Any] = {
    "main_profile": parse_person_main_profile,
    "experience": parse_experience,
    "education": parse_education,
    "interests": parse_interests,
    "honors": parse_honors,
    "languages": parse_languages,
    "posts": parse_person_posts,
    "recommendations": parse_recommendations,
    "contact_info": parse_contact_info,
}

_COMPANY_PARSERS: dict[str, Any] = {
    "about": parse_company_about,
    "posts": parse_company_posts,
    "jobs": parse_company_jobs,
}

_SEARCH_PARSERS: dict[str, Any] = {
    "search_people": parse_search_results_people,
    "search_jobs": parse_search_results_jobs,
}


# ── Router ────────────────────────────────────────────────────────────────────


def parse_section(
    section_name: str,
    html: str,
    entity_type: str = "person",
    *,
    include_raw: bool = False,
) -> ParsedSection:
    """Route a section to the appropriate typed parser.

    Args:
        section_name: Section key (e.g. "main_profile", "experience")
        html: HTML content extracted from the page
        entity_type: One of "person", "company", "search_people", "search_jobs", "job"
        include_raw: If True, attach source HTML to the model (debug mode)
    """
    parser = None

    if entity_type in ("search_people", "search_jobs"):
        parser = _SEARCH_PARSERS.get(entity_type)
    elif entity_type == "job":
        parser = parse_job_posting
    elif entity_type == "company":
        parser = _COMPANY_PARSERS.get(section_name)
    else:  # person
        parser = _PERSON_PARSERS.get(section_name)

    if parser is None:
        parser = parse_generic

    return parser(html, include_raw=include_raw)


# ── Layout support checks ─────────────────────────────────────────────────────

_SDUI_ISSUE_URL = "https://github.com/eliasbiondo/linkedin-mcp-server/issues/7"

SDUI_UNSUPPORTED_MESSAGE = (
    "LinkedIn served this page with its new server-driven UI (SDUI) markup, which "
    "the parser does not support yet, so no data could be extracted. Treat this "
    f"section as missing, not empty. See {_SDUI_ISSUE_URL}"
)

SDUI_EMPTY_SEARCH_MESSAGE = (
    "No results could be parsed from a search page LinkedIn served with its new "
    "server-driven UI (SDUI) markup. This layout is not fully supported yet, so "
    "results may be missing rather than genuinely empty. See "
    f"{_SDUI_ISSUE_URL}"
)


def is_empty_section(section: ParsedSection) -> bool:
    """Return True if a parsed model carries no data (ignoring the debug ``raw`` field)."""
    return all(not getattr(section, f.name) for f in fields(section) if f.name != "raw")


def unsupported_layout_reason(
    html: str,
    section: ParsedSection,
    *,
    message: str = SDUI_UNSUPPORTED_MESSAGE,
) -> str | None:
    """Explain an empty parse caused by a page layout the parsers do not support.

    Returns ``message`` when the parser extracted nothing from a page rendered
    with LinkedIn's SDUI markup, or None when the result should be trusted
    as-is (data found, or a legacy page that is genuinely empty).
    """
    if is_empty_section(section) and is_sdui_markup(html):
        return message
    return None


# ── Section validators ────────────────────────────────────────────────────────


def _validate_sections(
    sections: str | None,
    known_sections: dict[str, SectionConfig],
) -> tuple[set[str], list[str]]:
    """Parse comma-separated section names against a known section registry.

    Returns:
        Tuple of (valid_requested_sections, unknown_section_names)
    """
    if not sections:
        return set(), []

    requested = {s.strip() for s in sections.split(",") if s.strip()}
    known = set(known_sections.keys())
    valid = requested & known
    unknown = sorted(requested - known)
    return valid, unknown


def parse_person_sections(sections: str | None) -> tuple[set[str], list[str]]:
    """Parse comma-separated section names against known person sections."""
    return _validate_sections(sections, PERSON_SECTIONS)


def parse_company_sections(sections: str | None) -> tuple[set[str], list[str]]:
    """Parse comma-separated section names against known company sections."""
    return _validate_sections(sections, COMPANY_SECTIONS)
