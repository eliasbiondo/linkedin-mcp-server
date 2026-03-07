"""Session-related MCP tool registrations."""

from typing import Any

from fastmcp import Context, FastMCP

from linkedin_mcp_server.adapters.driving.error_mapping import map_domain_error
from linkedin_mcp_server.application.manage_session import ManageSessionUseCase


def register_session_tools(
    mcp: FastMCP,
    manage_session_uc: ManageSessionUseCase,
) -> None:
    """Register session-related MCP tools."""

    @mcp.tool(
        name="close_browser",
        description="Close the browser instance and release resources. Credentials are preserved.",
    )
    async def close_browser(ctx: Context) -> dict[str, Any]:
        try:
            result = await manage_session_uc.close_browser()
            return {
                "is_valid": result.is_valid,
                "message": result.message,
            }
        except Exception as e:
            map_domain_error(e, "close_browser")
