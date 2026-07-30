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
        albums           : numero de albumes publicados. Solo algunas fuentes
                           lo exponen; 0 significa "no publicado".
        top_track_rank   : media del rango de las canciones mas populares, en
                           la escala original de la fuente. Es el dato crudo
                           del que se deriva el indice de popularidad.

    Convencion importante: un 0 en una metrica puede significar dos cosas muy
    distintas —que el valor real sea cero, o que la fuente no publique ese
    dato—. Por eso `unavailable_metrics` declara explicitamente cuales no
    estan disponibles, y el reporte las distingue en lugar de mostrar "0".
    """

    artist_id: str
    name: str
    followers: int
    monthly_listeners: int
    popularity: int
    source: str
    captured_at: datetime
    albums: int = 0
    top_track_rank: int = 0
    unavailable_metrics: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        """Serializa a un diccionario apto para JSON."""
        data = asdict(self)
        data["captured_at"] = self.captured_at.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "ArtistData":
        """Reconstruye una instancia a partir de un diccionario JSON.

        Tolera instantaneas guardadas por versiones anteriores, que no
        incluian los campos anadidos despues.
        """
        payload = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}

        captured = payload.get("captured_at")
        if isinstance(captured, str):
            payload["captured_at"] = datetime.fromisoformat(captured)

        if "unavailable_metrics" in payload:
            payload["unavailable_metrics"] = tuple(payload["unavailable_metrics"])

        return cls(**payload)

    def is_available(self, metric: str) -> bool:
        """True si la fuente publica realmente esa metrica."""
        return metric not in self.unavailable_metrics

    @property
    def has_activity(self) -> bool:
        """True si el artista muestra alguna actividad registrada."""
        return self.followers > 0 or self.monthly_listeners > 0


@dataclass(frozen=True)
class Track:
    """Una cancion dentro del top de un artista.

    `rank` es el indice de popularidad que publica la fuente (0-1.000.000 en
    Deezer). No es un numero de reproducciones y no debe presentarse como tal.
    """

    position: int
    title: str
    album: str
    rank: int
    duration_seconds: int
    preview_url: str = ""
    link: str = ""

    @property
    def duration(self) -> str:
        """Duracion en formato mm:ss."""
        minutes, seconds = divmod(max(0, self.duration_seconds), 60)
        return f"{minutes}:{seconds:02d}"

    def to_dict(self) -> dict:
        data = asdict(self)
        data["duration"] = self.duration
        return data


def utcnow() -> datetime:
    """Momento actual en UTC, sin microsegundos (mas legible en los JSON)."""
    return datetime.now(timezone.utc).replace(microsecond=0)
