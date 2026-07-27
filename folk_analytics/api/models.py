"""Estructuras de datos compartidas."""

from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone


@dataclass(frozen=True)
class ArtistData:
    """Instantanea de las metricas de un artista en un momento dado.

    Attributes:
        artist_id        : identificador estable del artista.
        name             : nombre legible del artista.
        followers        : seguidores totales en la plataforma.
        monthly_listeners: oyentes mensuales. Puede ser 0 cuando la fuente
                           no expone el dato (la API publica de Spotify no
                           lo devuelve; solo aparece en la web).
        popularity       : indice 0-100 de popularidad relativa.
        source           : nombre del cliente que produjo el dato.
        captured_at      : momento de captura, en UTC.
    """

    artist_id: str
    name: str
    followers: int
    monthly_listeners: int
    popularity: int
    source: str
    captured_at: datetime

    def to_dict(self) -> dict:
        """Serializa a un diccionario apto para JSON."""
        data = asdict(self)
        data["captured_at"] = self.captured_at.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "ArtistData":
        """Reconstruye una instancia a partir de un diccionario JSON."""
        payload = dict(data)
        captured = payload["captured_at"]
        if isinstance(captured, str):
            payload["captured_at"] = datetime.fromisoformat(captured)
        return cls(**payload)

    @property
    def has_activity(self) -> bool:
        """True si el artista muestra alguna actividad registrada."""
        return self.followers > 0 or self.monthly_listeners > 0


def utcnow() -> datetime:
    """Momento actual en UTC, sin microsegundos (mas legible en los JSON)."""
    return datetime.now(timezone.utc).replace(microsecond=0)
