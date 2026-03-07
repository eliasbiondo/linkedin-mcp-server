"""Config port — abstracts configuration loading."""

from abc import ABC, abstractmethod

from linkedin_mcp_server.domain.value_objects import AppConfig


class ConfigPort(ABC):
    """Port for configuration loading and access."""

    @abstractmethod
    def load(self) -> AppConfig:
        """Load and return the complete application configuration.

        Implementations should handle:
        - Default values
        - Environment variables
        - CLI arguments
        - .env files
        - Validation

        Returns an immutable AppConfig.
        """
        ...
