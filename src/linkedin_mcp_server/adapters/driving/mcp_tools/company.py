"""Company-related MCP tool registrations."""

from typing import Any

from fastmcp import Context, FastMCP

from linkedin_mcp_server.adapters.driving.error_mapping import map_domain_error
from linkedin_mcp_server.adapters.driving.serialization import serialize_sections
from linkedin_mcp_server.application.scrape_company import ScrapeCompanyUseCase


def register_company_tools(
    mcp: FastMCP,
    scrape_company_uc: ScrapeCompanyUseCase,
) -> None:
    """Register company-related MCP tools."""

    @mcp.tool(
        name="get_company_profile",
        description=(
            "Get a specific company's LinkedIn profile.\n\n"
            "Args:\n"
            "    company_name: LinkedIn company name (e.g., 'google', 'stripe', 'openai')\n"
            "    sections: Comma-separated list of extra sections to scrape.\n"
            "        The about page is always included.\n"
            "        Available sections: posts, jobs\n"
            "        Default (None) scrapes only the about page."
        ),
    )
    async def get_company_profile(
        company_name: str,
        ctx: Context,
        sections: str | None = None,
    ) -> dict[str, Any]:
        try:
            result = await scrape_company_uc.execute(company_name, sections)
            response: dict[str, Any] = {
                "url": result.url,
                "sections": serialize_sections(result.sections),
            }
            if result.unknown_sections:
                response["unknown_sections"] = result.unknown_sections
            return response
        except Exception as e:
            map_domain_error(e, "get_company_profile")

    @mcp.tool(
        name="get_company_posts",
        description=(
            "Get recent posts from a company's LinkedIn feed.\n\n"
            "Args:\n"
            "    company_name: LinkedIn company name (e.g., 'google', 'stripe', 'openai')"
        ),
    )
    async def get_company_posts(
        company_name: str,
        ctx: Context,
    ) -> dict[str, Any]:
        try:
            result = await scrape_company_uc.execute(company_name, sections="posts")
            return {
                "url": result.url,
                "sections": serialize_sections(result.sections),
            }
        except Exception as e:
            map_domain_error(e, "get_company_posts")
