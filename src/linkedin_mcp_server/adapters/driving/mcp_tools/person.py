"""Person-related MCP tool registrations."""

from typing import Any

from fastmcp import Context, FastMCP

from linkedin_mcp_server.adapters.driving.error_mapping import map_domain_error
from linkedin_mcp_server.adapters.driving.serialization import serialize_sections
from linkedin_mcp_server.application.scrape_person import ScrapePersonUseCase
from linkedin_mcp_server.application.search_people import SearchPeopleUseCase


def register_person_tools(
    mcp: FastMCP,
    scrape_person_uc: ScrapePersonUseCase,
    search_people_uc: SearchPeopleUseCase,
) -> None:
    """Register person-related MCP tools."""

    @mcp.tool(
        name="get_person_profile",
        description=(
            "Get a specific person's LinkedIn profile.\n\n"
            "Args:\n"
            "    linkedin_username: LinkedIn username (e.g., 'satyanadella', 'jeffweiner08')\n"
            "    sections: Comma-separated list of extra sections to scrape.\n"
            "        The main profile page is always included.\n"
            "        Available sections: experience, education, interests, honors, "
            "languages, contact_info, posts\n"
            "        Default (None) scrapes only the main profile page."
        ),
    )
    async def get_person_profile(
        linkedin_username: str,
        ctx: Context,
        sections: str | None = None,
    ) -> dict[str, Any]:
        try:
            result = await scrape_person_uc.execute(linkedin_username, sections)
            response: dict[str, Any] = {
                "url": result.url,
                "sections": serialize_sections(result.sections),
            }
            if result.unknown_sections:
                response["unknown_sections"] = result.unknown_sections
            if result.failed_sections:
                response["failed_sections"] = result.failed_sections
            return response
        except Exception as e:
            map_domain_error(e, "get_person_profile")

    @mcp.tool(
        name="search_people",
        description=(
            "Search for people on LinkedIn.\n\n"
            "Args:\n"
            "    keywords: Search keywords (e.g., 'product manager', 'ML engineer at Meta')\n"
            "    location: Optional location filter (e.g., 'London', 'Berlin')"
        ),
    )
    async def search_people(
        keywords: str,
        ctx: Context,
        location: str | None = None,
    ) -> dict[str, Any]:
        try:
            result = await search_people_uc.execute(keywords, location)
            return {
                "url": result.url,
                "sections": serialize_sections(result.sections),
            }
        except Exception as e:
            map_domain_error(e, "search_people")
