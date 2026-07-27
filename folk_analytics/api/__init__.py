"""Clientes de datos de streaming.

Expone una interfaz unica (`StreamingClient`) implementada por:
  - `SimulatedClient`: datos sinteticos coherentes, sin red ni credenciales.
  - `SpotifyClient`  : API real de Spotify (requiere credenciales).

El resto del proyecto programa contra la interfaz, nunca contra una
implementacion concreta.
"""

from folk_analytics.api.base import (
    ArtistNotFoundError,
    StreamingAPIError,
    StreamingClient,
)
from folk_analytics.api.models import ArtistData
from folk_analytics.api.simulated import SimulatedClient

__all__ = [
    "ArtistData",
    "ArtistNotFoundError",
    "StreamingAPIError",
    "StreamingClient",
    "SimulatedClient",
]
