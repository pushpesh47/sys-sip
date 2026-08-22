"""Provider factory and registry."""

from typing import Optional

from app.config.settings import SipProviderConfig
from app.providers.base import GenericSipProvider, SipProvider
from app.providers.jio_fiber import JioFiberProvider


class ProviderRegistry:
    """Registry of available SIP providers."""

    _providers = {
        "jio_fiber": JioFiberProvider,
        "generic": GenericSipProvider,
    }

    @classmethod
    def get_provider_class(cls, provider_id: str) -> type[SipProvider]:
        """Get provider class by ID."""
        if provider_id not in cls._providers:
            raise ValueError(f"Unknown provider: {provider_id}")
        return cls._providers[provider_id]

    @classmethod
    def create_provider(cls, provider_id: str, config: Optional[SipProviderConfig] = None) -> SipProvider:
        """Create a provider instance."""
        provider_class = cls.get_provider_class(provider_id)
        return provider_class(config)

    @classmethod
    def list_providers(cls) -> list[str]:
        """List available provider IDs."""
        return list(cls._providers.keys())

    @classmethod
    def register_provider(cls, provider_id: str, provider_class: type[SipProvider]) -> None:
        """Register a new provider."""
        cls._providers[provider_id] = provider_class


def create_default_provider() -> SipProvider:
    """Create the default provider (Jio Fiber)."""
    return ProviderRegistry.create_provider("jio_fiber")