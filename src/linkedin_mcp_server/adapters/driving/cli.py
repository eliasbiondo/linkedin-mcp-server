"""CLI entry point — the main application entry point."""

import argparse
import asyncio
import logging
from dataclasses import replace

from linkedin_mcp_server.adapters.driven.env_config import EnvConfigAdapter
from linkedin_mcp_server.adapters.driving.mcp_server import create_mcp_server
from linkedin_mcp_server.container import Container


def _build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="linkedin-mcp-server",
        description="MCP server for LinkedIn scraping",
    )
    parser.add_argument(
        "--transport",
        choices=["stdio", "streamable-http"],
        help="MCP transport type (default: stdio)",
    )
    parser.add_argument(
        "--host",
        default=None,
        help="Host for HTTP transport (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="Port for HTTP transport (default: 8000)",
    )
    parser.add_argument(
        "--login",
        action="store_true",
        help="Open browser for interactive LinkedIn login",
    )
    parser.add_argument(
        "--logout",
        action="store_true",
        help="Clear stored credentials",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Check session status",
    )
    parser.add_argument(
        "--log-level",
        dest="log_level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Log level (default: WARNING)",
    )
    return parser


def main() -> None:
    """Main application entry point."""
    parser = _build_parser()
    args = parser.parse_args()

    # Load configuration
    config_adapter = EnvConfigAdapter(cli_args=args)
    config = config_adapter.load()

    # Configure logging
    logging.basicConfig(
        level=getattr(logging, config.server.log_level),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    # Build DI container
    container = Container(config)

    # Handle CLI commands
    if config.server.login:
        login_config = replace(config, browser=replace(config.browser, headless=False))
        login_container = Container(login_config)
        asyncio.run(_handle_login(login_container))
        return

    if config.server.logout:
        _handle_logout(container)
        return

    if config.server.status:
        asyncio.run(_handle_status(container))
        return

    # Create and run MCP server
    mcp = create_mcp_server(container)

    transport = config.server.transport
    if transport == "streamable-http":
        mcp.run(
            transport="streamable-http",
            host=config.server.host,
            port=config.server.port,
            path=config.server.path,
        )
    else:
        mcp.run(transport="stdio")


async def _handle_login(container: Container) -> None:
    """Handle --login command."""
    profile_path = container.auth.get_profile_path()

    print("\n  LinkedIn MCP Server — Login")
    print("  ─" * 20)
    print(f"  Profile: {profile_path}\n")

    try:
        result = await container.manage_session.login()
        print(f"  Status: {'Authenticated' if result.is_valid else 'Failed'}")
    except Exception as e:
        print(f"  {e}")
    finally:
        await container.browser.close()


async def _handle_status(container: Container) -> None:
    """Handle --status command."""
    result = await container.manage_session.check_status()
    print(f"\n  Status: {'Valid' if result.is_valid else 'Expired/Invalid'}")
    print(f"  Profile: {result.profile_path}")
    await container.browser.close()


def _handle_logout(container: Container) -> None:
    """Handle --logout command."""
    result = container.manage_session.logout()
    print(f"\n  {result.message}")
