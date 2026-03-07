"""MCP server factory — creates and configures the FastMCP server instance."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastmcp import FastMCP

from linkedin_mcp_server.adapters.driving.mcp_tools.company import register_company_tools
from linkedin_mcp_server.adapters.driving.mcp_tools.job import register_job_tools
from linkedin_mcp_server.adapters.driving.mcp_tools.person import register_person_tools
from linkedin_mcp_server.adapters.driving.mcp_tools.session import register_session_tools
from linkedin_mcp_server.container import Container

logger = logging.getLogger(__name__)


def create_mcp_server(container: Container) -> FastMCP:
    """Create MCP server with all tools registered via DI container."""

    @asynccontextmanager
    async def server_lifespan(app: FastMCP) -> AsyncIterator[dict]:
        logger.info("LinkedIn MCP Server starting...")
        yield {}
        logger.info("LinkedIn MCP Server shutting down...")
        await container.browser.close()

    mcp = FastMCP(
        "linkedin_mcp_server",
        lifespan=server_lifespan,
    )

    # Register all tools, injecting use cases from the container
    register_person_tools(mcp, container.scrape_person, container.search_people)
    register_company_tools(mcp, container.scrape_company)
    register_job_tools(mcp, container.scrape_job, container.search_jobs)
    register_session_tools(mcp, container.manage_session)

    return mcp
