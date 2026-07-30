"""Interfaz comun para cualquier fuente de datos de streaming."""

from __future__ import annotations

from abc import ABC, abstractmethod

from folk_analytics.api.models import ArtistData


class StreamingAPIError(Exception):
    """Fallo al comunicarse con la fuente de datos."""


class ArtistNotFoundError(StreamingAPIError):
    """El artista solicitado no existe en la fuente de datos."""


class StreamingClient(ABC):
    """Contrato que debe cumplir todo cliente de datos.

    Gracias a esta abstraccion, cambiar de datos simulados a la API real
    de Spotify no requiere tocar el agente, el analisis ni los reportes.
    """

    #: Identificador interno de la fuente. Se guarda en cada instantanea, asi
    #: que cambiarlo huerfanaria el historico ya recolectado.
    source_name: str = "base"

    #: Nombre que ve el usuario. Se separa del identificador precisamente para
    #: poder cambiar la etiqueta sin tocar los datos guardados.
    display_name: str = "base"

    @abstractmethod
    def fetch_artist(self, artist_name: str) -> ArtistData:
        """Recupera las metricas actuales de un artista.

        Args:
            artist_name: nombre del artista a consultar.

        Returns:
            Un `ArtistData` con las metricas del momento.

        Raises:
            ArtistNotFoundError: si el artista no existe en la fuente.
            StreamingAPIError  : ante cualquier otro fallo de la fuente.
        """

    @abstractmethod
    def available_artists(self) -> list[str]:
        """Lista de artistas conocidos, si la fuente puede enumerarlos."""

    def __repr__(self) -> str:
        return f"<{type(self).__name__} source={self.source_name!r}>"
