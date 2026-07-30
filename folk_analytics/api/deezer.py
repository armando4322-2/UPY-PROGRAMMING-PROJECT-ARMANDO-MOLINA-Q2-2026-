"""Cliente de la API publica de Deezer: la fuente de datos reales.

Deezer no exige credenciales ni registro, lo que la convierte en la unica
opcion viable para que el proyecto funcione con artistas reales tanto en
consola como en una pagina publica.

QUE PUBLICA Y QUE NO
--------------------
Deezer expone `nb_fan` (seguidores reales) y `nb_album`. **No publica**
oyentes mensuales ni un indice de popularidad. Esas metricas se marcan
como no disponibles en lugar de rellenarlas con ceros, porque un cero
significaria "el artista tiene cero oyentes", que es falso.

SIN HISTORICO RETROACTIVO
-------------------------
Ninguna API publica devuelve los seguidores que un artista tenia hace
treinta dias. Con esta fuente el agente empieza a acumular historico en su
primera ejecucion y las tendencias solo aparecen cuando hay suficientes
puntos reales. Es la limitacion honesta de trabajar con datos de verdad;
la fuente simulada existe precisamente para poder demostrar la deteccion
de tendencias sin esperar dias.

EL PROBLEMA DE LOS HOMONIMOS
----------------------------
Buscar "AURORA" y quedarse con el primer resultado devuelve un artista
homonimo de 2.486 seguidores en lugar de la AURORA noruega, que tiene mas
de medio millon y aparece en sexta posicion. La desambiguacion vive en
`api/matching.py`, compartida con las demas fuentes.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request

from folk_analytics import config
from folk_analytics.api.base import StreamingAPIError, StreamingClient
from folk_analytics.api.matching import match_score, normalize
from folk_analytics.api.matching import select_best_match as _select
from folk_analytics.api.models import ArtistData, Track, utcnow
from folk_analytics.logging_setup import get_logger

logger = get_logger("api.deezer")

#: Interfaz publica del modulo. `match_score` y `normalize` se reexportan a
#: proposito: viven en api/matching.py, pero forman parte de lo que este
#: modulo ofrece y los tests los importan desde aqui.
__all__ = [
    "DeezerClient",
    "PrefetchedDeezerClient",
    "match_score",
    "normalize",
    "parse_search_payload",
    "parse_top_tracks",
    "select_best_match",
    "to_artist_data",
]

SEARCH_URL = "https://api.deezer.com/search/artist"
TOP_TRACKS_URL = "https://api.deezer.com/artist/{artist_id}/top"
USER_AGENT = "FolkAnalytics/2.2 (proyecto academico UPY)"

#: Metricas que Deezer no publica. Se declaran para que el reporte pueda
#: distinguir "no disponible" de "cero".
UNAVAILABLE = ("monthly_listeners", "popularity")


def select_best_match(candidates: list[dict], query: str) -> dict:
    """Elige el artista correcto entre los resultados de Deezer.

    Envoltorio del criterio compartido, indicandole donde encontrar el
    nombre y el numero de seguidores en el formato de Deezer.
    """
    return _select(
        candidates,
        query,
        name_of=lambda c: c.get("name", ""),
        rank_of=lambda c: c.get("nb_fan", 0),
        source="Deezer",
    )


def to_artist_data(record: dict, source_name: str = "deezer") -> ArtistData:
    """Convierte un registro de artista de Deezer en un `ArtistData`."""
    return ArtistData(
        artist_id=f"DZ-{record['id']}",
        name=record.get("name", "").strip() or "Desconocido",
        followers=int(record.get("nb_fan", 0) or 0),
        monthly_listeners=0,   # no publicado por Deezer
        popularity=0,          # no publicado por Deezer
        source=source_name,
        captured_at=utcnow(),
        albums=int(record.get("nb_album", 0) or 0),
        unavailable_metrics=UNAVAILABLE,
    )


def parse_search_payload(payload: dict, query: str) -> ArtistData:
    """Interpreta la respuesta de busqueda de Deezer.

    Se mantiene como funcion independiente del transporte para que la
    consola (que hace la peticion con urllib) y la pagina web (que la hace
    con JSONP desde JavaScript, para sortear el bloqueo CORS de Deezer)
    compartan exactamente la misma logica de seleccion y conversion.
    """
    if not isinstance(payload, dict):
        raise StreamingAPIError("Deezer devolvio una respuesta con formato inesperado")

    if "error" in payload and payload["error"]:
        error = payload["error"]
        message = error.get("message", "error desconocido") if isinstance(error, dict) else str(error)
        raise StreamingAPIError(f"Deezer respondio con un error: {message}")

    best = select_best_match(payload.get("data") or [], query)
    return to_artist_data(best)


def parse_top_tracks(payload: dict, limit: int = 10) -> tuple[Track, ...]:
    """Interpreta la respuesta de top tracks de Deezer.

    Igual que el parseo de artistas, se mantiene independiente del transporte
    para que consola (urllib) y web (JSONP) compartan la misma logica.
    """
    if not isinstance(payload, dict):
        raise StreamingAPIError("Deezer devolvio una respuesta con formato inesperado")

    if payload.get("error"):
        error = payload["error"]
        message = error.get("message", "error desconocido") if isinstance(error, dict) else str(error)
        raise StreamingAPIError(f"Deezer respondio con un error: {message}")

    tracks = []
    for position, record in enumerate((payload.get("data") or [])[:limit], start=1):
        tracks.append(Track(
            position=position,
            title=(record.get("title") or "").strip() or "Sin titulo",
            album=((record.get("album") or {}).get("title") or "").strip(),
            rank=int(record.get("rank", 0) or 0),
            duration_seconds=int(record.get("duration", 0) or 0),
            preview_url=record.get("preview") or "",
            link=record.get("link") or "",
        ))
    return tuple(tracks)


class DeezerClient(StreamingClient):
    """Fuente de datos reales, sin credenciales."""

    source_name = "deezer"
    display_name = "Live stats \u00b7 datos reales"

    def __init__(self, timeout: int = 10, results_per_query: int = 10,
                 sleep_between_retries: bool = True):
        """
        Args:
            results_per_query: cuantos candidatos pedir. Con uno solo la
                desambiguacion es imposible; con diez basta para encontrar
                al artista correcto entre homonimos.
        """
        self.timeout = timeout
        self.results_per_query = results_per_query
        self.sleep_between_retries = sleep_between_retries

    # -- Transporte -----------------------------------------------------------

    def _request(self, artist_name: str) -> dict:
        """Consulta la API de busqueda, reintentando ante fallos pasajeros."""
        url = f"{SEARCH_URL}?" + urllib.parse.urlencode(
            {"q": artist_name, "limit": self.results_per_query}
        )
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})

        last_error: Exception | None = None

        for attempt in range(1, config.API_MAX_RETRIES + 1):
            try:
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    return json.loads(response.read().decode("utf-8"))
            except urllib.error.HTTPError as exc:
                last_error = exc
                # 429 y 5xx son transitorios; el resto no mejora reintentando.
                if exc.code != 429 and exc.code < 500:
                    raise StreamingAPIError(
                        f"Deezer devolvio HTTP {exc.code} para {artist_name!r}"
                    ) from exc
                logger.warning(
                    "Deezer devolvio HTTP %d (intento %d de %d)",
                    exc.code, attempt, config.API_MAX_RETRIES,
                )
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
                last_error = exc
                logger.warning(
                    "Fallo de red consultando Deezer (intento %d de %d): %s",
                    attempt, config.API_MAX_RETRIES, exc,
                )

            if self.sleep_between_retries and attempt < config.API_MAX_RETRIES:
                time.sleep(config.API_RETRY_BACKOFF_SECONDS * attempt)

        raise StreamingAPIError(
            f"No se pudo contactar con Deezer tras {config.API_MAX_RETRIES} "
            f"intentos: {last_error}"
        )

    # -- Interfaz publica -----------------------------------------------------

    def available_artists(self) -> list[str]:
        """Deezer no permite enumerar su catalogo: se busca por nombre."""
        return []

    def fetch_top_tracks(self, artist: ArtistData, limit: int = 10) -> tuple[Track, ...]:
        """Recupera las canciones mas populares de un artista.

        El identificador interno lleva el prefijo 'DZ-'; hay que quitarlo para
        componer la URL de la API.
        """
        numeric_id = artist.artist_id.removeprefix("DZ-")
        url = TOP_TRACKS_URL.format(artist_id=numeric_id) + "?" + urllib.parse.urlencode(
            {"limit": limit}
        )
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})

        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, json.JSONDecodeError, TimeoutError) as exc:
            # El top es informacion complementaria: si falla, el analisis debe
            # continuar igualmente en lugar de abortar.
            logger.warning("No se pudo recuperar el top de '%s': %s", artist.name, exc)
            return ()

        tracks = parse_top_tracks(payload, limit)
        logger.info("Top de '%s': %d canciones", artist.name, len(tracks))
        return tracks

    def fetch_artist(self, artist_name: str) -> ArtistData:
        """Recupera las metricas reales y actuales de un artista."""
        logger.info("Consultando la API de Deezer para '%s'", artist_name)

        payload = self._request(artist_name)
        data = parse_search_payload(payload, artist_name)

        logger.info(
            "Datos reales recibidos: %s (ID: %s, seguidores: %s, albumes: %d)",
            data.name, data.artist_id, f"{data.followers:,}", data.albums,
        )
        return data


class PrefetchedDeezerClient(DeezerClient):
    """Cliente de Deezer alimentado con una respuesta ya descargada.

    Deezer no envia cabeceras CORS, de modo que el navegador bloquea las
    peticiones directas. En la web es JavaScript quien obtiene la respuesta
    mediante JSONP y se la entrega a este cliente, que reutiliza intacta la
    logica de desambiguacion y conversion de la version de consola.
    """

    def __init__(self, payload: dict, top_payload: dict | None = None):
        super().__init__(sleep_between_retries=False)
        self._payload = payload
        self._top_payload = top_payload

    def _request(self, artist_name: str) -> dict:
        return self._payload

    def fetch_top_tracks(self, artist: ArtistData, limit: int = 10) -> tuple[Track, ...]:
        if self._top_payload is None:
            return ()
        return parse_top_tracks(self._top_payload, limit)
