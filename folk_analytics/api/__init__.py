"""Clientes de datos de streaming.

Expone una interfaz unica (`StreamingClient`) implementada por:
  - `SimulatedClient`: datos sinteticos coherentes, sin red ni credenciales.
  - `DeezerClient`   : datos reales sin credenciales (fuente real por defecto).

Spotify no aparece aqui a proposito: sus metricas no estan disponibles para
aplicaciones nuevas, asi que solo se usa como proveedor de fotos al generar
el catalogo (ver `api/spotify.py`).

El resto del proyecto programa contra la interfaz, nunca contra una
implementacion concreta.
"""

from folk_analytics.api.base import (
    ArtistNotFoundError,
    StreamingAPIError,
    StreamingClient,
)
from folk_analytics.api.models import ArtistData
from folk_analytics.api.deezer import DeezerClient
from folk_analytics.api.simulated import SimulatedClient

__all__ = [
    "ArtistData",
    "ArtistNotFoundError",
    "StreamingAPIError",
    "StreamingClient",
    "SimulatedClient",
    "DeezerClient",
]
