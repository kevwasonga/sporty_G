import logging

from ..config import settings
from .base import ProviderAdapter

logger = logging.getLogger("sporty.lab.providers")

# Test hook: tests register a lightweight fake provider under its own name and
# set PROVIDER=that_name. Wholly separate from the production sportybet provider.
_PROVIDER_REGISTRY: dict[str, type[ProviderAdapter]] = {}


def register_provider(name: str, cls: type[ProviderAdapter]) -> None:
    _PROVIDER_REGISTRY[name] = cls


def get_provider(name: str | None = None) -> ProviderAdapter:
    provider_name = (name or settings.provider).lower()

    if provider_name in _PROVIDER_REGISTRY:
        provider: ProviderAdapter = _PROVIDER_REGISTRY[provider_name]()
    elif provider_name == "sportybet":
        from .sportybet import SportyBetProvider

        provider = SportyBetProvider()
    else:
        raise ValueError(f"Unknown provider: {provider_name!r}")

    logger.info("Active provider: %s", provider.name)
    return provider


__all__ = ["ProviderAdapter", "get_provider", "register_provider"]