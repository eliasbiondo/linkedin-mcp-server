"""Person-related domain models."""

from dataclasses import dataclass, field


@dataclass
class PersonMainProfile:
    """Main profile page — extracted from /in/{username}/."""

    name: str | None = None
    headline: str | None = None
    location: str | None = None
    followers: str | None = None
    connections: str | None = None
    about: str | None = None
    profile_image_url: str | None = None
    raw: str | None = None


@dataclass
class ExperienceEntry:
    """A single work experience entry."""

    title: str | None = None
    company: str | None = None
    dates: str | None = None
    duration: str | None = None
    description: str | None = None
    company_logo_url: str | None = None


@dataclass
class ExperienceSection:
    """Experience section — extracted from /in/{username}/details/experience/."""

    experiences: list[ExperienceEntry] = field(default_factory=list)
    raw: str | None = None


@dataclass
class EducationEntry:
    """A single education entry."""

    school: str | None = None
    degree: str | None = None
    dates: str | None = None
    description: str | None = None
    school_logo_url: str | None = None


@dataclass
class EducationSection:
    """Education section — extracted from /in/{username}/details/education/."""

    education: list[EducationEntry] = field(default_factory=list)
    raw: str | None = None


@dataclass
class ContactInfo:
    """Contact info overlay — extracted from /in/{username}/overlay/contact-info/."""

    linkedin_url: str | None = None
    emails: list[str] = field(default_factory=list)
    phones: list[str] = field(default_factory=list)
    websites: list[str] = field(default_factory=list)
    birthday: str | None = None
    raw: str | None = None


@dataclass
class InterestEntry:
    """A single interest entry (person, company, group, etc.)."""

    name: str | None = None
    headline: str | None = None
    followers: str | None = None
    linkedin_url: str | None = None
    image_url: str | None = None


@dataclass
class InterestsSection:
    """Interests section — extracted from /in/{username}/details/interests/."""

    interests: list[InterestEntry] = field(default_factory=list)
    raw: str | None = None


@dataclass
class HonorEntry:
    """A single honor/award entry."""

    title: str | None = None
    issued_by: str | None = None
    description: str | None = None


@dataclass
class HonorsSection:
    """Honors & awards section — extracted from /in/{username}/details/honors/."""

    honors: list[HonorEntry] = field(default_factory=list)
    raw: str | None = None


@dataclass
class LanguageEntry:
    """A single language entry."""

    language: str | None = None
    proficiency: str | None = None


@dataclass
class LanguagesSection:
    """Languages section — extracted from /in/{username}/details/languages/."""

    languages: list[LanguageEntry] = field(default_factory=list)
    raw: str | None = None


@dataclass
class PersonPostEntry:
    """A single feed post entry."""

    author: str | None = None
    text: str | None = None
    posted_ago: str | None = None
    reactions: str | None = None
    activity_urn: str | None = None


@dataclass
class PersonPostsSection:
    """Posts section — extracted from /in/{username}/recent-activity/all/."""

    posts: list[PersonPostEntry] = field(default_factory=list)
    raw: str | None = None


@dataclass
class RecommendationEntry:
    """A single recommendation entry."""

    author: str | None = None
    author_headline: str | None = None
    relationship: str | None = None
    text: str | None = None
    author_url: str | None = None
    author_image_url: str | None = None


@dataclass
class RecommendationsSection:
    """Recommendations — extracted from /in/{username}/details/recommendations/."""

    received: list[RecommendationEntry] = field(default_factory=list)
    given: list[RecommendationEntry] = field(default_factory=list)
    raw: str | None = None


@dataclass
class GenericSection:
    """Fallback for sections without a dedicated parser."""

    content: str | None = None
    raw: str | None = None
