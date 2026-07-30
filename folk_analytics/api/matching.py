"""Desambiguacion de artistas por nombre.

Todas las APIs de musica devuelven varios candidatos ante una busqueda y
ninguna garantiza que el primero sea el correcto. El caso que motivo este
modulo: buscar "AURORA" en Deezer y quedarse con el primer resultado
devuelve un artista homonimo con 2.486 seguidores, mientras que la artista
noruega —con 551.254— aparece en sexta posicion. Un agente que analizara
al artista equivocado sin avisar seria peor que uno que fallara.

La logica vive aqui, separada de cualquier fuente concreta, para que Deezer
y Spotify compartan exactamente el mismo criterio en lugar de reimplementarlo
cada uno a su manera.
"""

from __future__ import annotations

import unicodedata
from typing import Callable, TypeVar

from folk_analytics.api.base import ArtistNotFoundError
from folk_analytics.logging_setup import get_logger

logger = get_logger("api.matching")

T = TypeVar("T")


def normalize(text: str) -> str:
    """Normaliza un nombre para poder compararlo.

    Quita acentos, unifica mayusculas, colapsa espacios, ignora la puntuacion
    y equipara las variantes de la conjuncion ("&" frente a "and"/"y"). Son
    las diferencias mas comunes entre como escribe el usuario y como registra
    el catalogo a un artista: "Iron & Wine" / "Iron and Wine",
    "Tyler The Creator" / "Tyler, The Creator".
    """
    text = unicodedata.normalize("NFKD", str(text))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.casefold().strip()
    text = text.replace("&", " and ").replace(" y ", " and ")

    # Los apostrofos se eliminan sin dejar hueco: "El De Las R's" y
    # "El De Las Rs" son el mismo artista, y sustituirlos por un espacio
    # daria "r s", que ya no coincide.
    for ch in "'\u2019\u02bc`":
        text = text.replace(ch, "")

    # El resto de la puntuacion si pasa a espacio, porque suele separar
    # palabras: "Tyler, The Creator" frente a "Tyler The Creator".
    for ch in ",.;:!?\"-_/\\()[]":
        text = text.replace(ch, " ")

    return " ".join(text.split())


def match_score(candidate_name: str, query: str) -> int:
    """Puntua cuanto se parece un candidato a lo que pidio el usuario.

    3 = coincidencia exacta
    2 = uno es prefijo del otro
    1 = uno contiene al otro
    0 = sin relacion (se descarta)
    """
    name, wanted = normalize(candidate_name), normalize(query)

    if not name or not wanted:
        return 0
    if name == wanted:
        return 3
    if name.startswith(wanted) or wanted.startswith(name):
        return 2
    if wanted in name or name in wanted:
        return 1
    return 0


def select_best_match(
    candidates: list[T],
    query: str,
    name_of: Callable[[T], str],
    rank_of: Callable[[T], int],
    source: str = "la fuente",
) -> T:
    """Elige el artista correcto entre los resultados de una busqueda.

    Ordena por calidad de coincidencia y, solo a igualdad, por popularidad.
    Ese orden importa: si se ordenara primero por seguidores, un artista
    enorme cuyo nombre apenas contiene la consulta secuestraria la busqueda
    de otro mas pequeño con nombre exacto.

    Args:
        candidates: resultados devueltos por la API.
        query     : lo que escribio el usuario.
        name_of   : extrae el nombre de un candidato.
        rank_of   : extrae la metrica de desempate (seguidores, fans...).
        source    : nombre de la fuente, solo para los mensajes de error.

    Raises:
        ArtistNotFoundError: si ningun candidato guarda relacion con la
            consulta.
    """
    if not candidates:
        raise ArtistNotFoundError(f"{source} no devolvio resultados para {query!r}")

    scored = [
        (match_score(name_of(c), query), int(rank_of(c) or 0), index, c)
        for index, c in enumerate(candidates)
    ]
    scored = [item for item in scored if item[0] > 0]

    if not scored:
        names = ", ".join(repr(name_of(c)) for c in candidates[:3])
        raise ArtistNotFoundError(
            f"Ningun resultado de {source} coincide con {query!r} (se obtuvo: {names})"
        )

    # El indice original se incluye al final para que el desempate sea
    # estable y el resultado no dependa del orden de iteracion.
    scored.sort(key=lambda item: (item[0], item[1], -item[2]), reverse=True)
    best_score, best_rank, _, best = scored[0]

    if len(scored) > 1:
        logger.debug(
            "Desambiguacion en %s: %d candidatos, elegido '%s' (%s, puntuacion %d)",
            source, len(scored), name_of(best), f"{best_rank:,}", best_score,
        )

    return best
