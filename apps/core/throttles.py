# apps/core/throttles.py

"""Zentrale Rate-Limits für das lokale Demo-Backend."""

from rest_framework.throttling import AnonRateThrottle, ScopedRateThrottle


class DemoApiRateThrottle(AnonRateThrottle):
    """Begrenzt allgemeine Demo-API-Aufrufe anhand der Client-IP."""

    scope = "demo_api"


class DemoBurstRateThrottle(AnonRateThrottle):
    """Begrenzt kurze Request-Spitzen ohne normale Bedienung zu stören."""

    scope = "demo_burst"


class UploadRateThrottle(ScopedRateThrottle):
    """Wendet das strengere Upload-Limit auf Upload-Endpunkte an."""
