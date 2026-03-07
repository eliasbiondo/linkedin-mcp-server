"""Job posting HTML parser.

Receives HTML and returns a typed model.
Handles LinkedIn's new SDUI layout with obfuscated CSS classes by using
data-attributes, semantic elements, heading text, and href patterns.
"""

import re

from bs4 import BeautifulSoup

from linkedin_mcp_server.domain.models.job import JobPostingDetail

_JOB_VIEW_RE = re.compile(r"/jobs/view/(\d+)")


def _text(el: object) -> str | None:
    """Return stripped visible text or None."""
    if el is None:
        return None
    txt = el.get_text(separator=" ", strip=True)
    return txt if txt else None


def _soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "html.parser")


def parse_job_posting(
    html: str, *, include_raw: bool = False
) -> JobPostingDetail:
    """Parse job posting detail page HTML.

    Extracts: title, company, location, posted_time, applicant_info,
    work_type (list of badges), description, job_id.
    """
    soup = _soup(html)

    # ── Job ID ────────────────────────────────────────────────────────
    job_id: str | None = None
    detail_div = soup.find(attrs={"data-view-name": "job-detail-page"})
    if detail_div:
        scope = detail_div.get("data-view-tracking-scope", "")
        m = re.search(r"jobPosting:(\d+)", scope)
        if m:
            job_id = m.group(1)
    if not job_id:
        # Fallback: look in any /jobs/view/XXXXX link
        link = soup.find("a", href=_JOB_VIEW_RE)
        if link:
            m = _JOB_VIEW_RE.search(link["href"])
            if m:
                job_id = m.group(1)

    # ── Company name ──────────────────────────────────────────────────
    company: str | None = None
    company_url: str | None = None
    company_logo_url: str | None = None
    company_link = soup.find(
        "a", href=re.compile(r"/company/[^/]+/life/?")
    )
    if company_link:
        label = company_link.get("aria-label", "")
        if label and "," in label:
            # "Company, Google."
            company = label.split(",", 1)[1].strip().rstrip(".")
        if not company:
            p_tag = company_link.find("p")
            if p_tag:
                a_inner = p_tag.find("a")
                company = _text(a_inner) if a_inner else _text(p_tag)
        # Company URL
        href = company_link.get("href", "")
        if href:
            company_url = href if href.startswith("http") else f"https://www.linkedin.com{href}"
        # Company logo from the same area
        logo_img = company_link.find("img")
        if logo_img:
            src = logo_img.get("src", "")
            if src:
                company_logo_url = src
    # Fallback logo: any img with company-logo in src
    if not company_logo_url:
        for img in soup.find_all("img"):
            src = img.get("src", "")
            if "company-logo" in src:
                company_logo_url = src
                break

    # ── Job title ─────────────────────────────────────────────────────
    title: str | None = None
    # The title is a <p> that contains the job title text and a verified badge
    # It's the first large-text <p> after the company logo section.
    # Look for the p containing the "Verified job" link
    verified_link = soup.find("a", attrs={"href": "#"})
    if verified_link:
        title_p = verified_link.parent
        if title_p and title_p.name == "p":
            title = _text(title_p)
            # Clean trailing "Verified job" text
            if title:
                title = re.sub(r"\s*Verified job\s*$", "", title).strip()
    if not title:
        # Fallback: look for the _0c38c653 class (title paragraph)
        title_p = soup.find("p", class_=lambda c: c and "_0c38c653" in c)
        if title_p:
            title = _text(title_p)
            if title:
                title = re.sub(r"\s*Verified job\s*$", "", title).strip()

    # ── Location / posted time / applicant info ───────────────────────
    location: str | None = None
    posted_time: str | None = None
    applicant_info: str | None = None

    # These are in a <p> with class _37677861 containing dots (·) as separators
    # after the title. Look for spans with _45102191 class for location-like text.
    meta_p_candidates = soup.find_all(
        "p", class_=lambda c: c and "_37677861" in c and "_837488b5" in c
    )
    for mp in meta_p_candidates:
        full = _text(mp)
        if not full:
            continue
        # Split by · and extract parts
        parts = [p.strip() for p in full.split("·")]
        if len(parts) >= 1 and not location:
            # First part with a comma is likely the location
            for part in parts:
                if "," in part and not location:
                    location = part
                elif re.search(
                    r"(hour|day|week|month|minute|ago|Reposted)",
                    part,
                    re.IGNORECASE,
                ):
                    # Clean bold markers from reposted
                    posted_time = re.sub(r"\s+", " ", part).strip()
                elif re.search(r"(clicked|appli)", part, re.IGNORECASE):
                    applicant_info = part
        if location:
            break

    # ── Work type badges ──────────────────────────────────────────────
    work_type: list[str] = []
    # Badges like "On-site", "Full-time" are in pill-like <span> elements
    # inside links to the job view URL
    badge_links = soup.find_all(
        "a",
        attrs={
            "href": _JOB_VIEW_RE,
            "class": lambda c: c and "fd9e0cf6" in c,
        },
    )
    for bl in badge_links:
        badge_span = bl.find(
            "span", class_=lambda c: c and "b043d390" in c
        )
        if badge_span:
            badge_text = _text(badge_span)
            if badge_text and badge_text not in ("Apply", "Save"):
                work_type.append(badge_text)

    # ── Job description ───────────────────────────────────────────────
    description: str | None = None
    about_slot = soup.find(
        "div",
        attrs={
            "data-sdui-component": lambda v: v
            and "aboutTheJob" in v
        },
    )
    if about_slot:
        # The expandable text box contains the full description
        text_box = about_slot.find(
            "span", attrs={"data-testid": "expandable-text-box"}
        )
        if text_box:
            description = _text(text_box)
            # Remove trailing "…more" button text
            if description:
                description = re.sub(r"\s*…\s*more\s*$", "", description)
    if not description:
        # Fallback: find "About the job" heading and grab the next text
        h2s = soup.find_all("h2")
        for h2 in h2s:
            if _text(h2) == "About the job":
                parent = h2.parent
                if parent:
                    desc_p = parent.find_next("p")
                    if desc_p:
                        text_box = desc_p.find(
                            "span",
                            attrs={"data-testid": "expandable-text-box"},
                        )
                        description = (
                            _text(text_box) if text_box else _text(desc_p)
                        )
                break

    return JobPostingDetail(
        title=title,
        company=company,
        company_url=company_url,
        company_logo_url=company_logo_url,
        location=location,
        posted_time=posted_time,
        applicant_info=applicant_info,
        work_type=work_type,
        description=description,
        job_id=job_id,
        raw=html if include_raw else None,
    )

