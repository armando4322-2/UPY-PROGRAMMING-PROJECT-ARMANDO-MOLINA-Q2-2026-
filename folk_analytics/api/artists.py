"""Catalogo de artistas destacados.

El catalogo se genera sin conexion con `tools/build_catalog.py` y se guarda
en `folk_analytics/data/catalog.json`. Contiene datos que casi no cambian
—identificadores, foto oficial, pais, generos— mientras que las metricas
volatiles (seguidores, albumes) se consultan en vivo en cada analisis.

Esa division importa: guardar los seguidores en el catalogo los dejaria
congelados en el dia de la generacion y el proyecto mostraria cifras
caducadas presentandolas como actuales.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

CATALOG_FILE = Path(__file__).resolve().parent.parent / "data" / "catalog.json"

#: Nombres de pais para las descripciones. Solo los presentes en el catalogo.
COUNTRIES = {
    "MX": "mexicano", "US": "estadounidense", "KR": "surcoreano",
    "ES": "espanol", "PR": "puertorriqueno", "CA": "canadiense",
    "GB": "britanico", "CL": "chileno", "JP": "japones", "AU": "australiano",
    "CO": "colombiano", "AR": "argentino", "VE": "venezolano",
}

FEMALE_COUNTRIES = {
    "mexicano": "mexicana", "estadounidense": "estadounidense",
    "surcoreano": "surcoreana", "espanol": "espanola",
    "puertorriqueno": "puertorriquena", "canadiense": "canadiense",
    "britanico": "britanica", "chileno": "chilena", "japones": "japonesa",
    "australiano": "australiana", "colombiano": "colombiana",
    "argentino": "argentina", "venezolano": "venezolana",
}


@dataclass(frozen=True)
class CatalogArtist:
    """Entrada del catalogo de artistas destacados."""

    name: str
    deezer_id: int | None = None
    spotify_id: str | None = None
    image: str | None = None
    country: str | None = None
    kind: str | None = None      # 'Person' o 'Group', segun MusicBrainz
    gender: str | None = None
    genres: tuple[str, ...] = ()
    began: str | None = None

    @property
    def description(self) -> str:
        """Descripcion breve construida a partir de datos reales.

        Se compone unicamente con lo que devuelven MusicBrainz y las APIs de
        musica: nada esta escrito a mano ni inventado sobre el artista.
        """
        parts: list[str] = []

        nationality = COUNTRIES.get((self.country or "").upper())
        if self.kind == "Group":
            noun = f"Grupo {nationality}" if nationality else "Grupo"
        elif nationality:
            if (self.gender or "").lower() == "female":
                nationality = FEMALE_COUNTRIES.get(nationality, nationality)
                noun = f"Artista {nationality}"
            else:
                noun = f"Artista {nationality}"
        else:
            noun = "Artista"
        parts.append(noun)

        if self.genres:
            parts.append(", ".join(self.genres[:3]))

        if self.began and len(self.began) >= 4:
            parts.append(
                f"activo desde {self.began[:4]}" if self.kind == "Group"
                else f"n. {self.began[:4]}"
            )

        return " · ".join(parts)


@lru_cache(maxsize=1)
def load_catalog() -> tuple[CatalogArtist, ...]:
    """Carga el catalogo del disco. Devuelve vacio si aun no se ha generado."""
    if not CATALOG_FILE.exists():
        return ()

    try:
        raw = json.loads(CATALOG_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return ()

    return tuple(
        CatalogArtist(
            name=item["name"],
            deezer_id=item.get("deezer_id"),
            spotify_id=item.get("spotify_id"),
            image=item.get("image"),
            country=item.get("country"),
            kind=item.get("kind"),
            gender=item.get("gender"),
            genres=tuple(item.get("genres", [])),
            began=item.get("began"),
        )
        for item in raw.get("artists", [])
    )


def catalog_names() -> list[str]:
    """Nombres de los artistas destacados, en el orden del catalogo."""
    return [a.name for a in load_catalog()]


def find(name: str) -> CatalogArtist | None:
    """Busca una entrada del catalogo por nombre, ignorando mayusculas."""
    from folk_analytics.api.matching import normalize

    wanted = normalize(name)
    for artist in load_catalog():
        if normalize(artist.name) == wanted:
            return artist
    return None


def suggest(prefix: str, limit: int = 8) -> list[str]:
    """Sugerencias de autocompletado para el catalogo.

    Prioriza los nombres que empiezan por lo tecleado sobre los que solo lo
    contienen, que es el orden que un usuario espera al escribir.
    """
    from folk_analytics.api.matching import normalize

    typed = normalize(prefix)
    if not typed:
        return []

    starts, contains = [], []
    for artist in load_catalog():
        name = normalize(artist.name)
        if name.startswith(typed):
            starts.append(artist.name)
        elif typed in name:
            contains.append(artist.name)

    return (starts + contains)[:limit]
