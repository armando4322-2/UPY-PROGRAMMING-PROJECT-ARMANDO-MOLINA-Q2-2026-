"""Indice de popularidad derivado de datos reales.

POR QUE EXISTE
--------------
Ninguna de las fuentes disponibles publica un indice de popularidad por
artista. Spotify lo tenia, pero dejo de exponerlo a las aplicaciones nuevas
(verificado el 2026-07-30: 403 en /v1/artists?ids= y campo ausente en
/v1/artists/{id}). Deezer nunca lo ha publicado.

Lo que Deezer SI publica es el `rank` de cada cancion: un entero en el rango
0-1.000.000 que refleja su popularidad relativa dentro de la plataforma. A
partir de los rangos de las canciones mas escuchadas de un artista se puede
componer un indice comparable entre artistas.

LA FORMULA
----------
    indice = media(rank de las N canciones mas populares) / 10.000

El divisor convierte el rango 0-1.000.000 de Deezer a una escala 0-100, que
es la habitual para este tipo de indicadores y la que ya usaba el proyecto.

Se usa la MEDIA y no el maximo a proposito: un unico exito viral dispararia
el maximo y describiria mal a un artista cuyo repertorio restante apenas se
escucha. La media de las diez canciones principales mide fondo de catalogo,
no un pico aislado.

QUE ES Y QUE NO ES
------------------
Es un indicador **calculado por este proyecto** a partir de datos reales.
NO es una metrica oficial de ninguna plataforma, y no debe presentarse como
tal en ningun sitio: ni en el reporte, ni en la web, ni en la documentacion.
Tampoco es un numero de reproducciones.

Su utilidad esta en comparar artistas entre si y en seguir su evolucion, no
en el valor absoluto.
"""

from __future__ import annotations

from folk_analytics.api.models import Track
from folk_analytics.logging_setup import get_logger

logger = get_logger("analytics.popularity")

#: Rango maximo que publica Deezer para el `rank` de una cancion.
SOURCE_RANK_MAX = 1_000_000

#: Escala del indice resultante.
INDEX_MAX = 100

#: Descripcion corta y reutilizable, para que la etiqueta sea identica en
#: todas las superficies y no se degrade a "popularidad" a secas.
INDEX_LABEL = "indice calculado sobre los rangos reales de las canciones"


def mean_track_rank(tracks: tuple[Track, ...] | list[Track]) -> float:
    """Media del `rank` de las canciones dadas.

    Es el dato crudo de Deezer, sin transformar: sirve para mostrar el
    alcance real del repertorio junto al indice derivado.
    """
    ranks = [track.rank for track in tracks if track.rank > 0]
    if not ranks:
        return 0.0
    return sum(ranks) / len(ranks)


def popularity_index(tracks: tuple[Track, ...] | list[Track]) -> int:
    """Calcula el indice de popularidad 0-100.

    Args:
        tracks: canciones mas populares del artista, tal y como las devuelve
            la fuente. Se ignoran las que no traen rango.

    Returns:
        Un entero de 0 a 100. Devuelve 0 si no hay ninguna cancion con rango,
        que es el caso de un artista sin actividad registrada.
    """
    average = mean_track_rank(tracks)
    if average <= 0:
        return 0

    index = round(average / SOURCE_RANK_MAX * INDEX_MAX)
    index = max(0, min(INDEX_MAX, index))

    logger.debug(
        "Indice de popularidad: %d (media de %d canciones, rank medio %.0f)",
        index, len([t for t in tracks if t.rank > 0]), average,
    )
    return index
