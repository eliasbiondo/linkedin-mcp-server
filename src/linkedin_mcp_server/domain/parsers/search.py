"""Search results HTML parsers.

All functions receive HTML and return typed models.
Handles both LinkedIn's SDUI layout (people search) and classic Ember
layout (job search).
"""

import re

from bs4 import BeautifulSoup

from linkedin_mcp_server.domain.models.search import (
    JobSearchResultEntry,
    JobSearchResults,
    PeopleSearchResults,
    PersonSearchResult,
)

_PROFILE_URL_RE = re.compile(r"/in/([^/]+?)(?:/[a-z]{2})?/?$")
_JOB_VIEW_RE = re.compile(r"/jobs/view/(\d+)/")


def _text(el: object) -> str | None:
    """Return stripped visible text or None."""
    if el is None:
        return None
    txt = el.get_text(separator=" ", strip=True)
    return txt if txt else None


def _soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "html.parser")


# ── People Search parser ─────────────────────────────────────────────────────


def parse_search_results_people(
    html: str, *, include_raw: bool = False
) -> PeopleSearchResults:
    """Parse people search results page HTML.

    Extracts list of PersonSearchResult from SDUI search result cards.
    Each card is identified by data-view-name="people-search-result".
    """
    soup = _soup(html)
    results: list[PersonSearchResult] = []

    cards = soup.find_all(
        attrs={"data-view-name": "people-search-result"}
    )

    for card in cards:
        # Profile URL and username from the main <a> link
        profile_link = card.find(
            "a",
            attrs={"data-view-name": "search-result-lockup-title"},
        )
        profile_url: str | None = None
        linkedin_username: str | None = None
        name: str = ""

        if profile_link:
            name = _text(profile_link) or ""
            href = profile_link.get("href", "")
            if href:
                profile_url = href
                m = _PROFILE_URL_RE.search(href)
                if m:
                    linkedin_username = m.group(1)

        if not name:
            continue

        # Connection degree from <span class="_45102191">
        connection_degree = ""
        degree_container = card.find(
            "span", class_=lambda c: c and "_45102191" in c
        )
        if degree_container:
            degree_text = _text(degree_container)
            if degree_text:
                # Extract "1st", "2nd", "3rd" etc.
                m = re.search(r"(\d+(?:st|nd|rd|th))", degree_text)
                if m:
                    connection_degree = m.group(1)

        # Profile image from <figure> with aria-label
        profile_image_url: str | None = None
        figure = card.find("figure", attrs={"data-view-name": "image"})
        if figure:
            img = figure.find("img")
            if img:
                src = img.get("src", "")
                if src and "profile-displayphoto" in src:
                    profile_image_url = src

        # Headline — first <p> with _37677861 class in name's parent
        headline: str | None = None
        location: str | None = None

        # The listitem div contains the name + headline + location in order
        listitem = card.find("div", attrs={"role": "listitem"})
        if listitem:
            # Find all <p> with _37677861 class that are direct text content
            info_divs = listitem.find_all(
                "div",
                class_=lambda c: c
                and "_04bda81b" in c
                and "_9dfef8a0" in c
                and "_837488b5" in c,
            )
            for i, div in enumerate(info_divs):
                p = div.find("p", class_=lambda c: c and "_37677861" in c)
                if p:
                    text = _text(p)
                    if text:
                        if i == 0:
                            headline = text
                        elif i == 1:
                            location = text

        # Mutual connections from social proof insight
        mutual_connections: str | None = None
        social_proof_links = card.find_all(
            "a",
            attrs={"data-view-name": "search-result-social-proof-insight"},
        )
        for sp_link in social_proof_links:
            sp_text = _text(sp_link)
            if sp_text and "mutual connection" in sp_text.lower():
                mutual_connections = sp_text

        # Followers from social proof
        followers: str | None = None
        for sp_link in social_proof_links:
            sp_text = _text(sp_link)
            if sp_text and "follower" in sp_text.lower():
                followers = sp_text

        results.append(
            PersonSearchResult(
                name=name,
                connection_degree=connection_degree,
                headline=headline,
                location=location,
                mutual_connections=mutual_connections,
                followers=followers,
                profile_url=profile_url,
                linkedin_username=linkedin_username,
                profile_image_url=profile_image_url,
            )
        )

    return PeopleSearchResults(
        people=results,
        raw=html if include_raw else None,
    )


# ── Job Search parser ────────────────────────────────────────────────────────


def parse_search_results_jobs(
    html: str, *, include_raw: bool = False
) -> JobSearchResults:
    """Parse job search results page HTML.

    Uses the classic Ember layout with job-card-container divs.
    Extracts job_id, title, company, location, insight, and metadata.
    """
    soup = _soup(html)
    results: list[JobSearchResultEntry] = []

    # Total results from the header subtitle
    total_results: str | None = None
    subtitle = soup.find(
        "div",
        class_=lambda c: c
        and "jobs-search-results-list__subtitle" in c,
    )
    if subtitle:
        total_results = _text(subtitle)

    # Each job card has a data-job-id attribute
    cards = soup.find_all(
        "div",
        attrs={"data-job-id": True},
        class_=lambda c: c and "job-card-container" in c,
    )

    for card in cards:
        job_id = card.get("data-job-id")

        # Title from the link's aria-label
        title: str | None = None
        job_url: str | None = None
        title_link = card.find(
            "a", class_=lambda c: c and "job-card-container__link" in c
        )
        if title_link:
            label = title_link.get("aria-label", "")
            if label:
                # Clean "with verification" suffix
                title = re.sub(
                    r"\s+with verification$", "", label
                ).strip()
            href = title_link.get("href", "")
            if href:
                m = _JOB_VIEW_RE.search(href)
                job_url = (
                    f"https://www.linkedin.com/jobs/view/{m.group(1)}/"
                    if m
                    else None
                )

        # Company from artdeco-entity-lockup__subtitle
        company: str | None = None
        company_el = card.find(
            "div",
            class_=lambda c: c
            and "artdeco-entity-lockup__subtitle" in c,
        )
        if company_el:
            company = _text(company_el)

        # Location from metadata wrapper
        location: str | None = None
        location_li = card.find(
            "li",
            class_=lambda c: c and "pJCTyyZHJEwdnAZhBTBVMaBZjcFmTQ" in c,
        )
        if location_li:
            location = _text(location_li)

        # Insight text (e.g., "Actively reviewing applicants")
        insight: str | None = None
        insight_el = card.find(
            "div", class_="job-card-container__job-insight-text"
        )
        if insight_el:
            insight = _text(insight_el)

        # Footer metadata items (Viewed, Promoted, Be an early applicant)
        metadata_parts: list[str] = []
        footer_items = card.find_all(
            "li",
            class_=lambda c: c
            and "job-card-container__footer-item" in c,
        )
        for fi in footer_items:
            fi_text = _text(fi)
            if fi_text:
                metadata_parts.append(fi_text)
        metadata = " · ".join(metadata_parts) if metadata_parts else None

        # Company logo URL from the card's logo image
        company_logo_url: str | None = None
        logo_div = card.find(
            "div", class_=lambda c: c and "job-card-list__logo" in c
        )
        if logo_div:
            img = logo_div.find("img")
            if img:
                src = img.get("src", "")
                if src:
                    company_logo_url = src

        results.append(
            JobSearchResultEntry(
                title=title,
                company=company,
                location=location,
                job_id=job_id,
                job_url=job_url,
                company_logo_url=company_logo_url,
                insight=insight,
                metadata=metadata,
            )
        )

    return JobSearchResults(
        total_results=total_results,
        jobs=results,
        raw=html if include_raw else None,
    )
