"""Company profile HTML parsers.

All functions receive HTML and return typed models.
"""

import re

from bs4 import BeautifulSoup, Tag

from linkedin_mcp_server.domain.models.company import (
    CompanyAbout,
    CompanyJobEntry,
    CompanyJobsSection,
    CompanyPostEntry,
    CompanyPostsSection,
)

# ── Helpers ──────────────────────────────────────────────────────────────────

_PROMO_URN_PREFIX = "urn:li:inAppPromotion"


def _text(element: Tag | None) -> str | None:
    """Extract visible text from an element, stripping whitespace."""
    if element is None:
        return None
    text = element.get_text(separator=" ", strip=True)
    text = re.sub(r"\s+", " ", text).strip()
    return text or None


def _soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "lxml")


# ── Company About parser ────────────────────────────────────────────────────


def parse_company_about(html: str, *, include_raw: bool = False) -> CompanyAbout:
    """Parse company about/overview page HTML.

    Extracts: name, overview, website, phone, industry, company_size,
    headquarters, type, founded, specialties, followers, employees_on_linkedin.
    """
    soup = _soup(html)

    # Company name — <h1> with org-top-card-summary__title class
    name: str | None = None
    h1 = soup.find(
        "h1",
        class_=lambda c: c and "org-top-card-summary__title" in c,
    )
    if h1:
        name = _text(h1)

    # Top card info items (industry, location, followers, employees)
    followers: str | None = None
    employees_on_linkedin: str | None = None
    info_items = soup.find_all(
        "div",
        class_="org-top-card-summary-info-list__info-item",
    )
    for item in info_items:
        text = _text(item)
        if not text:
            continue
        if "follower" in text.lower():
            followers = text.strip()
        elif "employee" in text.lower():
            employees_on_linkedin = text.strip()

    # Overview text — <p> with break-words class in the about section
    overview: str | None = None
    overview_el = soup.find(
        "p",
        class_=lambda c: c and "break-words" in c and "white-space-pre-wrap" in c,
    )
    if overview_el:
        overview = _text(overview_el)

    # Parse <dl> definition list for structured details
    details: dict[str, str] = {}
    dl = soup.find("dl")
    if dl:
        dts = dl.find_all("dt")
        for dt in dts:
            h3 = dt.find("h3")
            key = _text(h3) if h3 else _text(dt)
            if not key:
                continue
            key_lower = key.lower().strip()

            # Find the next <dd> sibling(s)
            dd = dt.find_next_sibling("dd")
            if dd:
                # For links, extract the href text
                link = dd.find("a")
                if link and key_lower == "website":
                    span = link.find("span")
                    value = _text(span) if span else _text(link)
                else:
                    value = _text(dd)

                if value:
                    details[key_lower] = value

                    # Company size may have a second <dd> with associated members
                    if key_lower == "company size":
                        dd2 = dd.find_next_sibling("dd")
                        if dd2:
                            assoc = _text(dd2)
                            if assoc and "associated" in assoc.lower():
                                details["associated_members"] = assoc

    # Map details to model fields
    website = details.get("website")
    phone = details.get("phone")
    industry = details.get("industry")
    company_size = details.get("company size")
    if "associated_members" in details:
        company_size = (
            f"{company_size} ({details['associated_members']})"
            if company_size
            else details["associated_members"]
        )
    headquarters = details.get("headquarters")
    company_type = details.get("type")
    founded = details.get("founded")
    specialties = details.get("specialties")

    # Company logo URL from top card image
    logo_url: str | None = None
    logo_img = soup.find(
        "img",
        class_=lambda c: c and "org-top-card-primary-content__logo" in c,
    )
    if not logo_img:
        # Fallback: any img in the top card section
        top_card = soup.find("section", class_="org-top-card")
        if top_card:
            logo_img = top_card.find("img")
    if logo_img:
        src = logo_img.get("src", "")
        if src:
            logo_url = src

    return CompanyAbout(
        name=name,
        overview=overview,
        website=website,
        phone=phone,
        industry=industry,
        company_size=company_size,
        headquarters=headquarters,
        type=company_type,
        founded=founded,
        specialties=specialties,
        followers=followers,
        employees_on_linkedin=employees_on_linkedin,
        logo_url=logo_url,
        raw=html if include_raw else None,
    )


# ── Company Posts parser ─────────────────────────────────────────────────────


def _aria_hidden_text(element: Tag | None) -> str | None:
    """Extract the aria-hidden='true' span text for display values."""
    if element is None:
        return None
    span = element.find("span", attrs={"aria-hidden": "true"})
    return _text(span) if span else _text(element)


def parse_company_posts(
    html: str, *, include_raw: bool = False
) -> CompanyPostsSection:
    """Parse company posts feed HTML.

    Extracts list of CompanyPostEntry (text, time_posted, reactions,
    comments, reposts).  Promotional items are skipped.
    """
    soup = _soup(html)
    entries: list[CompanyPostEntry] = []

    articles = soup.find_all(
        "div",
        class_=lambda c: c and "feed-shared-update-v2" in c,
        attrs={"role": "article"},
    )

    for article in articles:
        # Skip promos
        urn = article.get("data-urn", "")
        if urn.startswith(_PROMO_URN_PREFIX):
            continue

        # Post text
        text_el = article.find(
            "div",
            class_=lambda c: c and "update-components-text" in c,
        )
        text: str | None = None
        if text_el:
            span = text_el.find("span", class_="break-words")
            text = _text(span) if span else _text(text_el)

        # Time posted
        time_el = article.find(
            "span",
            class_=lambda c: c
            and "update-components-actor__sub-description" in c,
        )
        time_posted = _aria_hidden_text(time_el)
        # Clean trailing bullet / globe icon noise
        if time_posted:
            time_posted = re.sub(r"\s*•.*$", "", time_posted).strip()

        # Reactions count
        reactions_el = article.find(
            "span",
            class_=lambda c: c
            and "social-details-social-counts__reactions-count" in c,
        )
        reactions = _text(reactions_el)

        # Comments count
        comments_btn = article.find(
            "button",
            attrs={"aria-label": lambda v: v and "comment" in v.lower()},
        )
        comments: str | None = None
        if comments_btn:
            span = comments_btn.find("span", attrs={"aria-hidden": "true"})
            comments = _text(span) if span else None

        # Reposts count
        reposts_btn = article.find(
            "button",
            attrs={"aria-label": lambda v: v and "repost" in v.lower()},
        )
        reposts: str | None = None
        if reposts_btn:
            span = reposts_btn.find("span", attrs={"aria-hidden": "true"})
            reposts = _text(span) if span else None

        entries.append(
            CompanyPostEntry(
                text=text,
                time_posted=time_posted,
                reactions=reactions,
                comments=comments,
                reposts=reposts,
            )
        )

    return CompanyPostsSection(
        posts=entries,
        raw=html if include_raw else None,
    )


# ── Company Jobs parser ──────────────────────────────────────────────────────

_JOB_ID_RE = re.compile(r"currentJobId=(\d+)")


def parse_company_jobs(
    html: str, *, include_raw: bool = False
) -> CompanyJobsSection:
    """Parse company jobs page HTML.

    Extracts total_openings and a list of CompanyJobEntry from both the
    \"Recommended\" and \"Recently posted\" carousels.
    """
    soup = _soup(html)
    entries: list[CompanyJobEntry] = []

    # Total openings headline
    total_openings: str | None = None
    headline = soup.find(
        "h4",
        class_=lambda c: c
        and "org-jobs-job-search-form-module__headline" in c,
    )
    if headline:
        total_openings = _text(headline)

    # Job cards appear inside <section class="job-card-container ...">
    cards = soup.find_all(
        "section",
        class_=lambda c: c and "job-card-container" in c,
    )

    for card in cards:
        # Title from aria-hidden span > strong
        title_div = card.find("div", class_="job-card-square__title")
        title: str | None = None
        if title_div:
            hidden_span = title_div.find(
                "span", attrs={"aria-hidden": "true"}
            )
            if hidden_span:
                strong = hidden_span.find("strong")
                title = _text(strong) if strong else _text(hidden_span)

        # Job ID and URL from href
        job_id: str | None = None
        job_url: str | None = None
        link = card.find("a", class_=lambda c: c and "job-card-square__link" in c)
        if link:
            href = link.get("href", "")
            m = _JOB_ID_RE.search(href)
            if m:
                job_id = m.group(1)
                job_url = f"https://www.linkedin.com/jobs/view/{job_id}/"

        # Company name
        company_div = card.find("div", class_="job-card-container__company-name")
        company = _text(company_div)

        # Location
        location_span = card.find(
            "span", class_="pJCTyyZHJEwdnAZhBTBVMaBZjcFmTQ"
        )
        location = _text(location_span)

        # Posted time from <time> element
        time_el = card.find("time")
        posted_time = _text(time_el)

        entries.append(
            CompanyJobEntry(
                title=title,
                job_id=job_id,
                job_url=job_url,
                company=company,
                location=location,
                posted_time=posted_time,
            )
        )

    return CompanyJobsSection(
        total_openings=total_openings,
        jobs=entries,
        raw=html if include_raw else None,
    )
