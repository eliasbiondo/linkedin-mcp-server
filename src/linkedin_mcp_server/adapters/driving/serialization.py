"""Serialization utilities for converting typed models to JSON-serializable dicts."""

from dataclasses import asdict
from typing import Any

from linkedin_mcp_server.domain.parsers import ParsedSection


def serialize_section(section: ParsedSection) -> dict[str, Any]:
    """Convert a typed model to a JSON-serializable dict, stripping None values."""
    return {k: v for k, v in asdict(section).items() if v is not None}


def serialize_sections(sections: dict[str, Any]) -> dict[str, Any]:
    """Serialize all sections in a response, stripping None values from each."""
    return {name: serialize_section(section) for name, section in sections.items()}
