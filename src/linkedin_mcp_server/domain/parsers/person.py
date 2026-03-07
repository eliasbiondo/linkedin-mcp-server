"""Person profile HTML parsers.

All functions receive HTML and return typed models.
Uses BeautifulSoup for robust HTML parsing.
"""

import re

from bs4 import BeautifulSoup, Tag

from linkedin_mcp_server.domain.models.person import (
    ContactInfo,
    EducationEntry,
    EducationSection,
    ExperienceEntry,
    ExperienceSection,
    GenericSection,
    HonorEntry,
    HonorsSection,
    InterestEntry,
    InterestsSection,
    LanguageEntry,
    LanguagesSection,
    PersonMainProfile,
    PersonPostEntry,
    PersonPostsSection,
    RecommendationEntry,
    RecommendationsSection,
)

# ── Helpers ──────────────────────────────────────────────────────────────────


def _text(element: Tag | None) -> str | None:
    """Extract visible text from an element, stripping whitespace."""
    if element is None:
        return None
    text = element.get_text(separator=" ", strip=True)
    # Collapse multiple whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text or None


def _aria_hidden_text(element: Tag | None) -> str | None:
    """Extract the aria-hidden='true' span text for display values."""
    if element is None:
        return None
    span = element.find("span", attrs={"aria-hidden": "true"})
    return _text(span) if span else _text(element)


def _soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "lxml")


def _split_dates_duration(raw: str | None) -> tuple[str | None, str | None]:
    """Split 'Sep 2022 - Feb 2025 · 2 yrs 6 mos' into (dates, duration)."""
    if not raw:
        return None, None
    parts = raw.split(" · ", 1)
    dates = parts[0].strip() if parts else None
    duration = parts[1].strip() if len(parts) > 1 else None
    return dates, duration


def _extract_description(entity: Tag) -> str | None:
    """Extract description text from sub-components, excluding skills lines."""
    sub = entity.find("div", class_=lambda c: c and "pvs-entity__sub-components" in c)
    if not sub:
        return None

    lines: list[str] = []
    for span in sub.find_all("span", attrs={"aria-hidden": "true"}, recursive=True):
        text = _text(span)
        if not text:
            continue
        # Skip skills lines
        if text.startswith("Skills:") or text.startswith("Skills :"):
            continue
        # Skip if parent is a bold-only wrapper (already captured as title)
        parent_div = span.find_parent(
            "div", class_=lambda c: c and "t-bold" in c if c else False
        )
        if parent_div:
            continue
        lines.append(text)

    return "\n".join(lines) if lines else None


# ── Main profile parser ─────────────────────────────────────────────────────


def parse_person_main_profile(html: str, *, include_raw: bool = False) -> PersonMainProfile:
    """Parse a person's main LinkedIn profile page HTML.

    Extracts: name, headline, location, followers, connections, about.
    """
    soup = _soup(html)

    # ── Name ──────────────────────────────────────────────────────────────
    name: str | None = None
    h1 = soup.find("h1")
    if h1:
        name = _text(h1)

    # ── Headline ──────────────────────────────────────────────────────────
    headline: str | None = None
    headline_el = soup.find("div", class_="text-body-medium")
    if headline_el:
        headline = _text(headline_el)

    # ── Location ──────────────────────────────────────────────────────────
    location: str | None = None
    location_el = soup.find(
        "span",
        class_=lambda c: (
            c
            and "text-body-small" in c
            and "break-words" in c
            and "t-black--light" in c
        ),
    )
    if location_el:
        # Make sure it's not inside the followers/connections area
        parent_ul = location_el.find_parent("ul")
        if parent_ul is None:
            location = _text(location_el)

    # Fallback: search for location by structure
    if not location:
        for span in soup.find_all(
            "span", class_=lambda c: c and "text-body-small" in c
        ):
            classes = span.get("class", [])
            if "t-black--light" in classes and "break-words" in classes and "inline" in classes:
                text = _text(span)
                if text and "follower" not in text.lower() and "connection" not in text.lower():
                    location = text
                    break

    # ── Followers & Connections ───────────────────────────────────────────
    followers: str | None = None
    connections: str | None = None

    for li in soup.find_all("li", class_=lambda c: c and "text-body-small" in c):
        text = _text(li)
        if not text:
            continue
        lower = text.lower()
        if "follower" in lower:
            followers = text
        elif "connection" in lower:
            connections = text

    # ── About ─────────────────────────────────────────────────────────────
    about: str | None = None
    for section in soup.find_all("section"):
        anchor = section.find("div", id="about")
        if anchor:
            about_container = section.find(
                "div",
                class_=lambda c: c and "inline-show-more-text" in c if c else False,
            )
            if about_container:
                about_span = about_container.find("span", attrs={"aria-hidden": "true"})
                about = _text(about_span) if about_span else _text(about_container)
            break

    # ── Profile image ─────────────────────────────────────────────────────
    profile_image_url: str | None = None
    profile_img = soup.find(
        "img",
        class_=lambda c: c and "pv-top-card-profile-picture__image" in c,
    )
    if profile_img:
        src = profile_img.get("src", "")
        if src and "profile-displayphoto" in src:
            profile_image_url = src

    return PersonMainProfile(
        name=name,
        headline=headline,
        location=location,
        followers=followers,
        connections=connections,
        about=about,
        profile_image_url=profile_image_url,
        raw=html if include_raw else None,
    )


# ── Experience parser ────────────────────────────────────────────────────────


def _parse_experience_entity(entity: Tag, parent_company: str | None = None) -> ExperienceEntry:
    """Parse a single profile-component-entity into an ExperienceEntry."""
    # Title is always the bold text
    title_el = entity.find("div", class_=lambda c: c and "t-bold" in c)
    title = _aria_hidden_text(title_el)

    # Company and employment info from t-14 t-normal spans (non-caption)
    company = parent_company
    info_spans = entity.find_all(
        "span", class_=lambda c: c and "t-14" in c and "t-normal" in c and "t-black--light" not in c
    )
    for span in info_spans:
        # Skip caption wrappers (they hold dates)
        if span.find(class_="pvs-entity__caption-wrapper"):
            continue
        text = _aria_hidden_text(span)
        if text and not company:
            # For standalone entries: "Company · Employment type"
            company = text.split(" · ")[0].strip() if " · " in text else text

    # Dates & duration from pvs-entity__caption-wrapper
    caption = entity.find("span", class_="pvs-entity__caption-wrapper")
    caption_text = _aria_hidden_text(caption) if caption else None
    dates, duration = _split_dates_duration(caption_text)

    # Description from sub-components
    description = _extract_description(entity)

    # Company logo URL
    company_logo_url: str | None = None
    img = entity.find("img", class_=lambda c: c and "EntityPhoto" in c)
    if img:
        src = img.get("src", "")
        if src:
            company_logo_url = src

    return ExperienceEntry(
        title=title,
        company=company,
        dates=dates,
        duration=duration,
        description=description,
        company_logo_url=company_logo_url,
    )


def parse_experience(html: str, *, include_raw: bool = False) -> ExperienceSection:
    """Parse experience section HTML.

    Handles two LinkedIn patterns:
    - Standalone entries: title + company in a single entity
    - Company groups: company as parent with nested role sub-entries
    """
    soup = _soup(html)
    entries: list[ExperienceEntry] = []

    # Top-level experience items
    top_items = soup.find_all(
        "li",
        class_=lambda c: c and "pvs-list__paged-list-item" in c and "artdeco-list__item" in c,
    )

    for item in top_items:
        entity = item.find(
            "div", attrs={"data-view-name": "profile-component-entity"}, recursive=True
        )
        if not entity:
            continue

        # Check if this is a company group (has nested sub-entities with divider spans)
        nested_container = entity.find("div", class_="pvs-list__container")
        if nested_container:
            # Company group: extract company name from bold text
            company_el = entity.find("div", class_=lambda c: c and "t-bold" in c)
            company_name = _aria_hidden_text(company_el)

            # Find all nested role entities
            nested_entities = nested_container.find_all(
                "div", attrs={"data-view-name": "profile-component-entity"}, recursive=True
            )
            for nested in nested_entities:
                entries.append(_parse_experience_entity(nested, parent_company=company_name))
        else:
            # Standalone entry
            entries.append(_parse_experience_entity(entity))

    return ExperienceSection(
        experiences=entries,
        raw=html if include_raw else None,
    )


# ── Education parser ─────────────────────────────────────────────────────────


def parse_education(html: str, *, include_raw: bool = False) -> EducationSection:
    """Parse education section HTML.

    Extracts list of EducationEntry (school, degree, dates, description).
    """
    soup = _soup(html)
    entries: list[EducationEntry] = []

    items = soup.find_all(
        "li",
        class_=lambda c: c and "pvs-list__paged-list-item" in c and "artdeco-list__item" in c,
    )

    for item in items:
        entity = item.find(
            "div", attrs={"data-view-name": "profile-component-entity"}, recursive=True
        )
        if not entity:
            continue

        # School name — bold text
        school_el = entity.find("div", class_=lambda c: c and "t-bold" in c)
        school = _aria_hidden_text(school_el)

        # Degree — first t-14 t-normal span (non-caption, non-light)
        degree: str | None = None
        info_spans = entity.find_all(
            "span",
            class_=lambda c: (
                c and "t-14" in c and "t-normal" in c and "t-black--light" not in c
            ),
        )
        for span in info_spans:
            if span.find(class_="pvs-entity__caption-wrapper"):
                continue
            degree = _aria_hidden_text(span)
            if degree:
                break

        # Dates from pvs-entity__caption-wrapper
        caption = entity.find("span", class_="pvs-entity__caption-wrapper")
        dates = _aria_hidden_text(caption) if caption else None

        # Description from sub-components (e.g. "Full scholarship.")
        description: str | None = None
        sub = entity.find(
            "div", class_=lambda c: c and "pvs-entity__sub-components" in c
        )
        if sub:
            desc_lines: list[str] = []
            for span in sub.find_all(
                "span", attrs={"aria-hidden": "true"}, recursive=True
            ):
                text = _text(span)
                if text:
                    desc_lines.append(text)
            description = "\n".join(desc_lines) if desc_lines else None

        # School logo URL
        school_logo_url: str | None = None
        img = entity.find("img", class_=lambda c: c and "EntityPhoto" in c)
        if img:
            src = img.get("src", "")
            if src:
                school_logo_url = src

        entries.append(
            EducationEntry(
                school=school, degree=degree, dates=dates,
                description=description, school_logo_url=school_logo_url,
            )
        )

    return EducationSection(
        education=entries,
        raw=html if include_raw else None,
    )


# ── Contact info parser ──────────────────────────────────────────────────────


def parse_contact_info(html: str, *, include_raw: bool = False) -> ContactInfo:
    """Parse contact info overlay HTML.

    Extracts: linkedin_url, emails, phones, websites, birthday.
    """
    soup = _soup(html)

    linkedin_url: str | None = None
    emails: list[str] = []
    phones: list[str] = []
    websites: list[str] = []
    birthday: str | None = None

    # Each contact type is a <section class="pv-contact-info__contact-type">
    for section in soup.find_all("section", class_="pv-contact-info__contact-type"):
        header = section.find("h3")
        if not header:
            continue
        header_text = _text(header) or ""
        header_lower = header_text.lower()

        if "profile" in header_lower:
            # LinkedIn profile URL
            link = section.find("a", href=True)
            if link:
                linkedin_url = link["href"].strip()

        elif "website" in header_lower:
            # Website links
            for link in section.find_all("a", href=True):
                url = link["href"].strip()
                if url:
                    websites.append(url)

        elif "phone" in header_lower:
            # Phone numbers
            for li in section.find_all("li"):
                # Phone is in a <span class="t-14 t-black t-normal">
                span = li.find(
                    "span",
                    class_=lambda c: (
                        c and "t-black" in c and "t-normal" in c and "t-black--light" not in c
                    ),
                )
                if span:
                    phone = _text(span)
                    if phone:
                        phones.append(phone)

        elif "email" in header_lower:
            # Email addresses
            for link in section.find_all("a", href=True):
                href = link["href"].strip()
                if href.startswith("mailto:"):
                    emails.append(href[7:])  # Strip "mailto:"
                else:
                    email_text = _text(link)
                    if email_text and "@" in email_text:
                        emails.append(email_text)

        elif "birthday" in header_lower:
            # Birthday
            span = section.find("span", class_=lambda c: c and "t-normal" in c)
            birthday = _text(span)

    return ContactInfo(
        linkedin_url=linkedin_url,
        emails=emails,
        phones=phones,
        websites=websites,
        birthday=birthday,
        raw=html if include_raw else None,
    )


# ── Interests parser ─────────────────────────────────────────────────────────


def parse_interests(
    html: str, *, include_raw: bool = False
) -> InterestsSection:
    """Parse interests section HTML.

    Extracts entity entries (name, headline, followers, url)
    from the active tab.
    """
    soup = _soup(html)

    # Parse entries from the active tab panel
    entries: list[InterestEntry] = []
    items = soup.find_all(
        "li",
        class_=lambda c: (
            c and "pvs-list__paged-list-item" in c and "artdeco-list__item" in c
        ),
    )

    for item in items:
        entity = item.find(
            "div",
            attrs={"data-view-name": "profile-component-entity"},
            recursive=True,
        )
        if not entity:
            continue

        # Name — bold text
        name_el = entity.find("div", class_=lambda c: c and "t-bold" in c)
        name = _aria_hidden_text(name_el)

        # Headline — first t-14 t-normal span (not light, not caption)
        headline: str | None = None
        info_spans = entity.find_all(
            "span",
            class_=lambda c: (
                c
                and "t-14" in c
                and "t-normal" in c
                and "t-black--light" not in c
            ),
        )
        for span in info_spans:
            if span.find(class_="pvs-entity__caption-wrapper"):
                continue
            # Skip supplementary info (e.g. "· 2nd")
            if "pvs-entity__supplementary-info" in (span.get("class") or []):
                continue
            headline = _aria_hidden_text(span)
            if headline:
                break

        # Followers from pvs-entity__caption-wrapper
        caption = entity.find("span", class_="pvs-entity__caption-wrapper")
        followers = _aria_hidden_text(caption) if caption else None

        # LinkedIn URL from the first <a> with an href to linkedin.com
        linkedin_url: str | None = None
        link = entity.find("a", href=True)
        if link:
            href = link["href"].strip()
            if "linkedin.com" in href:
                linkedin_url = href

        # Entity image URL (person photo or company logo)
        image_url: str | None = None
        img = entity.find("img", class_=lambda c: c and "EntityPhoto" in c)
        if img:
            src = img.get("src", "")
            if src:
                image_url = src

        entries.append(
            InterestEntry(
                name=name,
                headline=headline,
                followers=followers,
                linkedin_url=linkedin_url,
                image_url=image_url,
            )
        )

    return InterestsSection(
        interests=entries,
        raw=html if include_raw else None,
    )


# ── Honors parser ────────────────────────────────────────────────────────────


def parse_honors(
    html: str, *, include_raw: bool = False
) -> HonorsSection:
    """Parse honors & awards section HTML.

    Extracts list of HonorEntry (title, issued_by, description).
    """
    soup = _soup(html)
    entries: list[HonorEntry] = []

    items = soup.find_all(
        "li",
        class_=lambda c: (
            c and "pvs-list__paged-list-item" in c and "artdeco-list__item" in c
        ),
    )

    for item in items:
        entity = item.find(
            "div",
            attrs={"data-view-name": "profile-component-entity"},
            recursive=True,
        )
        if not entity:
            continue

        # Title — bold text
        title_el = entity.find("div", class_=lambda c: c and "t-bold" in c)
        title = _aria_hidden_text(title_el)

        # Issued by — first t-14 t-normal span (e.g. "Issued by X · Jan 2009")
        issued_by: str | None = None
        # Look in the main content area for the issued-by span
        main_content = entity.find(
            "div", class_=lambda c: c and "flex-grow-1" in c
        )
        if main_content:
            for span in main_content.find_all(
                "span",
                class_=lambda c: (
                    c
                    and "t-14" in c
                    and "t-normal" in c
                    and "t-black--light" not in c
                ),
            ):
                if span.find(class_="pvs-entity__caption-wrapper"):
                    continue
                issued_by = _aria_hidden_text(span)
                if issued_by:
                    break

        # Description from sub-components
        description: str | None = None
        sub = entity.find(
            "div", class_=lambda c: c and "pvs-entity__sub-components" in c
        )
        if sub:
            desc_lines: list[str] = []
            for span in sub.find_all(
                "span", attrs={"aria-hidden": "true"}, recursive=True
            ):
                text = _text(span)
                if text and not text.startswith("Associated with"):
                    desc_lines.append(text)
            description = "\n".join(desc_lines) if desc_lines else None

        entries.append(
            HonorEntry(
                title=title,
                issued_by=issued_by,
                description=description,
            )
        )

    return HonorsSection(
        honors=entries,
        raw=html if include_raw else None,
    )


# ── Languages parser ─────────────────────────────────────────────────────────


def parse_languages(
    html: str, *, include_raw: bool = False
) -> LanguagesSection:
    """Parse languages section HTML.

    Extracts list of LanguageEntry (language, proficiency).
    """
    soup = _soup(html)
    entries: list[LanguageEntry] = []

    items = soup.find_all(
        "li",
        class_=lambda c: (
            c and "pvs-list__paged-list-item" in c and "artdeco-list__item" in c
        ),
    )

    for item in items:
        entity = item.find(
            "div",
            attrs={"data-view-name": "profile-component-entity"},
            recursive=True,
        )
        if not entity:
            continue

        # Language name — bold text
        name_el = entity.find("div", class_=lambda c: c and "t-bold" in c)
        language = _aria_hidden_text(name_el)

        # Proficiency from pvs-entity__caption-wrapper
        caption = entity.find("span", class_="pvs-entity__caption-wrapper")
        proficiency = _aria_hidden_text(caption) if caption else None

        entries.append(
            LanguageEntry(language=language, proficiency=proficiency)
        )

    return LanguagesSection(
        languages=entries,
        raw=html if include_raw else None,
    )


# ── Posts parser ─────────────────────────────────────────────────────────────


def parse_person_posts(
    html: str, *, include_raw: bool = False
) -> PersonPostsSection:
    """Parse person posts / recent-activity HTML.

    Extracts individual post entries.
    """
    soup = _soup(html)

    # Parse individual posts
    entries: list[PersonPostEntry] = []
    articles = soup.find_all(
        "div",
        class_=lambda c: c and "feed-shared-update-v2" in c,
        attrs={"data-urn": True},
    )

    for article in articles:
        activity_urn = article.get("data-urn")

        # Author name
        author_el = article.find(
            "span", class_=lambda c: c and "update-components-actor__title" in c
        )
        author = _aria_hidden_text(author_el) if author_el else None

        # Posted ago (e.g. "2w", "1mo") from sub-description visually-hidden
        posted_ago: str | None = None
        sub_desc = article.find(
            "span",
            class_=lambda c: (
                c and "update-components-actor__sub-description" in c
            ),
        )
        if sub_desc:
            vh = sub_desc.find("span", class_="visually-hidden")
            if vh:
                raw_text = _text(vh) or ""
                # e.g. "2 weeks ago · Visible to anyone..."
                parts = raw_text.split(" \u2022 ")
                if parts:
                    posted_ago = parts[0].strip()

        # Post text content
        post_text: str | None = None
        commentary = article.find(
            "div",
            class_=lambda c: (
                c and "update-components-update-v2__commentary" in c
            ),
        )
        if commentary:
            # Remove hidden spans to avoid duplication
            for vh in commentary.find_all(class_="visually-hidden"):
                vh.decompose()
            post_text = commentary.get_text(separator=" ", strip=True)
            # Clean up extra whitespace
            post_text = re.sub(r"\s{2,}", " ", post_text).strip()
            post_text = post_text.replace(" \u2026more", "").strip()

        # Reactions count
        reactions: str | None = None
        # Try social-proof fallback number first
        proof = article.find(
            "span",
            class_=lambda c: (
                c
                and "social-details-social-counts__social-proof-fallback-number"
                in c
            ),
        )
        if proof:
            reactions = _text(proof)
        else:
            # Fall back to reactions-count span
            count_el = article.find(
                "span",
                class_=lambda c: (
                    c
                    and "social-details-social-counts__reactions-count" in c
                ),
            )
            if count_el:
                reactions = _text(count_el)

        entries.append(
            PersonPostEntry(
                author=author,
                text=post_text,
                posted_ago=posted_ago,
                reactions=reactions,
                activity_urn=activity_urn,
            )
        )

    return PersonPostsSection(
        posts=entries,
        raw=html if include_raw else None,
    )


# ── Recommendations parser ──────────────────────────────────────────────────


def parse_recommendations(
    html: str, *, include_raw: bool = False
) -> RecommendationsSection:
    """Parse recommendations section HTML.

    Separates recommendations into received and given based on
    LinkedIn's tab panel structure.
    """
    soup = _soup(html)

    def _parse_entries_from_container(container: Tag) -> list[RecommendationEntry]:
        """Parse recommendation entries from a container element."""
        entries: list[RecommendationEntry] = []
        items = container.find_all(
            "li",
            class_=lambda c: (
                c
                and "pvs-list__paged-list-item" in c
                and "artdeco-list__item" in c
            ),
        )

        for item in items:
            entity = item.find(
                "div",
                attrs={"data-view-name": "profile-component-entity"},
                recursive=True,
            )
            if not entity:
                continue

            # Author name — bold text
            name_el = entity.find(
                "div", class_=lambda c: c and "t-bold" in c
            )
            author = _aria_hidden_text(name_el)

            # Author headline — first t-14 t-normal span (not light)
            author_headline: str | None = None
            main_content = entity.find(
                "div", class_=lambda c: c and "flex-grow-1" in c
            )
            if main_content:
                for span in main_content.find_all(
                    "span",
                    class_=lambda c: (
                        c
                        and "t-14" in c
                        and "t-normal" in c
                        and "t-black--light" not in c
                    ),
                    recursive=True,
                ):
                    if span.find(class_="pvs-entity__caption-wrapper"):
                        continue
                    if "pvs-entity__supplementary-info" in (
                        span.get("class") or []
                    ):
                        continue
                    author_headline = _aria_hidden_text(span)
                    if author_headline:
                        break

            # Relationship from pvs-entity__caption-wrapper
            caption = entity.find(
                "span", class_="pvs-entity__caption-wrapper"
            )
            relationship = _aria_hidden_text(caption) if caption else None

            # Recommendation text from sub-components
            text: str | None = None
            sub = entity.find(
                "div",
                class_=lambda c: c and "pvs-entity__sub-components" in c,
            )
            if sub:
                text_lines: list[str] = []
                for span in sub.find_all(
                    "span",
                    attrs={"aria-hidden": "true"},
                    recursive=True,
                ):
                    t = _text(span)
                    if t:
                        text_lines.append(t)
                text = "\n".join(text_lines) if text_lines else None

            # Author LinkedIn URL
            author_url: str | None = None
            link = entity.find("a", href=True)
            if link:
                href = link["href"].strip()
                if "linkedin.com" in href:
                    author_url = href

            # Author image URL
            author_image_url: str | None = None
            img = entity.find("img", class_=lambda c: c and "EntityPhoto" in c)
            if img:
                src = img.get("src", "")
                if src:
                    author_image_url = src

            # Skip empty entries
            if not author and not text:
                continue

            entries.append(
                RecommendationEntry(
                    author=author,
                    author_headline=author_headline,
                    relationship=relationship,
                    text=text,
                    author_url=author_url,
                    author_image_url=author_image_url,
                )
            )

        return entries

    received: list[RecommendationEntry] = []
    given: list[RecommendationEntry] = []

    # LinkedIn uses tab buttons + tabpanels. Identify tab IDs.
    tab_buttons = soup.find_all("button", attrs={"role": "tab"})

    # Map tab panel IDs to "received" or "given"
    tab_map: dict[str, str] = {}
    for btn in tab_buttons:
        btn_text = _text(btn) or ""
        btn_lower = btn_text.lower()
        controls = btn.get("aria-controls", "")
        if "received" in btn_lower and controls:
            tab_map[controls] = "received"
        elif "given" in btn_lower and controls:
            tab_map[controls] = "given"

    if tab_map:
        # Parse each tab panel separately
        for panel_id, category in tab_map.items():
            panel = soup.find(id=panel_id)
            if panel:
                entries = _parse_entries_from_container(panel)
                if category == "received":
                    received = entries
                else:
                    given = entries
    else:
        # Fallback: no tab structure found, treat all as received
        received = _parse_entries_from_container(soup)

    return RecommendationsSection(
        received=received,
        given=given,
        raw=html if include_raw else None,
    )


# ── Generic parser ───────────────────────────────────────────────────────────


def parse_generic(html: str, *, include_raw: bool = False) -> GenericSection:
    """Fallback parser for sections without a dedicated parser.

    Returns the text content extracted from the HTML.
    """
    soup = _soup(html)

    # Remove script and style tags
    for tag in soup(["script", "style", "svg"]):
        tag.decompose()

    # Remove visually-hidden elements (duplicated a11y text)
    for el in soup.find_all(class_="visually-hidden"):
        el.decompose()

    text = soup.get_text(separator="\n", strip=True)
    # Collapse multiple blank lines
    text = re.sub(r"\n{3,}", "\n\n", text).strip()

    return GenericSection(
        content=text or None,
        raw=html if include_raw else None,
    )
