"""Spotify como proveedor de identidad e imagen.

POR QUE NO ES UNA FUENTE DE ANALISIS
------------------------------------
Este modulo empezo siendo un `StreamingClient` que debia aportar seguidores
y popularidad. Al ejecutarlo por primera vez contra la API real, con
credenciales validas, se comprobo que Spotify ya no expone esos datos a las
aplicaciones nuevas.

Verificado el 2026-07-30 con un token de Client Credentials valido:

    GET /v1/search?type=artist        200  -> objeto simplificado:
                                             external_urls, href, id, images,
                                             name, type, uri
    GET /v1/artists/{id}              200  -> las MISMAS claves. Sin
                                             followers, popularity ni genres
    GET /v1/artists?ids={id}          403  Forbidden
    GET /v1/artists/{id}/top-tracks   403  Forbidden
    GET /v1/artists/{id}/albums       200

Es decir: la autenticacion funciona y la busqueda tambien, pero las metricas
no llegan. Usar Spotify para analizar devolveria cero seguidores en todos los
artistas, lo que pareceria un fallo del proyecto cuando en realidad es una
restriccion de la plataforma.

QUE SI APORTA
-------------
Fotografias oficiales en alta resolucion (hasta 640x640) e identificadores
canonicos. Eso es lo que se usa, y solo en tiempo de generacion del catalogo
(`tools/build_catalog.py`), nunca durante el analisis. El resultado queda
guardado en `folk_analytics/data/catalog.json`, de modo que ni la version de
consola ni la pagina web necesitan credenciales para mostrar las fotos.

Para metricas reales, la fuente verificada es `DeezerClient`.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

from folk_analytics import config
from folk_analytics.api.base import StreamingAPIError
from folk_analytics.api.matching import select_best_match
from folk_analytics.logging_setup import get_logger

logger = get_logger("api.spotify")

SEARCH_URL = "https://api.spotify.com/v1/search"
USER_AGENT = "FolkAnalytics/2.3 (proyecto academico UPY)"

#: Claves que la API devuelve realmente en un objeto artista. Se documenta
#: aqui porque es distinto de lo que describe la documentacion publica.
OBSERVED_ARTIST_KEYS = ("external_urls", "href", "id", "images", "name", "type", "uri")


def load_credentials() -> tuple[str, str]:
    """Lee las credenciales del entorno o del archivo .env.

    Raises:
        StreamingAPIError: si faltan, con instrucciones para obtenerlas.
    """
    env_path = config.PROJECT_ROOT / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())

    client_id = os.environ.get("SPOTIFY_CLIENT_ID", "")
    secret = os.environ.get("SPOTIFY_CLIENT_SECRET", "")

    if not client_id or not secret:
        raise StreamingAPIError(
            "Faltan credenciales de Spotify. Copia .env.example a .env y rellena "
            "SPOTIFY_CLIENT_ID y SPOTIFY_CLIENT_SECRET. Se obtienen en "
            "https://developer.spotify.com/dashboard"
        )
    return client_id, secret


def parse_search_payload(payload: dict, query: str) -> dict:
    """Elige el artista correcto entre los resultados y devuelve su identidad.

    Returns:
        Diccionario con `spotify_id`, `name` e `image` (o None si no hay).

    Raises:
        ArtistNotFoundError: si ningun resultado coincide con la consulta.
        StreamingAPIError  : si la respuesta trae un error o no es valida.
    """
    if not isinstance(payload, dict):
        raise StreamingAPIError("Spotify devolvio una respuesta con formato inesperado")

    if payload.get("error"):
        error = payload["error"]
        message = error.get("message", "error desconocido") if isinstance(error, dict) else str(error)
        raise StreamingAPIError(f"Spotify respondio con un error: {message}")

    items = (payload.get("artists") or {}).get("items") or []

    # La busqueda no ordena por relevancia de nombre, asi que el primer
    # resultado puede ser un homonimo. Sin metricas que usar como desempate,
    # el criterio es unicamente la calidad de la coincidencia y el orden que
    # devuelve Spotify, que ya refleja su propia relevancia.
    best = select_best_match(
        items, query,
        name_of=lambda c: c.get("name", ""),
        rank_of=lambda c: 0,
        source="Spotify",
    )

    images = best.get("images") or []
    return {
        "spotify_id": best["id"],
        "name": best.get("name", ""),
        "image": images[0]["url"] if images else None,
    }


class SpotifyImageProvider:
    """Obtiene fotos oficiales e identificadores canonicos de Spotify.

    No implementa `StreamingClient` a proposito: no puede aportar metricas,
    y hacerlo pasar por una fuente de analisis daria datos vacios con
    apariencia de validos.
    """

    source_name = "spotify"

    def __init__(self, client_id: str | None = None, client_secret: str | None = None,
                 results_per_query: int = 10):
        if client_id and client_secret:
            self.client_id, self.client_secret = client_id, client_secret
        else:
            self.client_id, self.client_secret = load_credentials()

        self.results_per_query = results_per_query
        self._token: str | None = None
        self._token_expires_at = 0.0

    def _get_token(self) -> str:
        """Obtiene y cachea un token de aplicacion."""
        if self._token and time.time() < self._token_expires_at - 60:
            return self._token

        body = urllib.parse.urlencode({
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }).encode()

        request = urllib.request.Request(
            config.SPOTIFY_TOKEN_URL, data=body,
            headers={"Content-Type": "application/x-www-form-urlencoded",
                     "User-Agent": USER_AGENT},
        )

        try:
            with urllib.request.urlopen(request, timeout=15) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, json.JSONDecodeError, TimeoutError) as exc:
            logger.error("Fallo la autenticacion con Spotify: %s", exc)
            raise StreamingAPIError(f"No se pudo autenticar con Spotify: {exc}") from exc

        self._token = payload["access_token"]
        self._token_expires_at = time.time() + payload.get("expires_in", 3600)
        logger.info("Token de Spotify obtenido correctamente")
        return self._token

    def fetch_identity(self, artist_name: str) -> dict:
        """Busca un artista y devuelve su identificador y su foto oficial."""
        token = self._get_token()
        url = SEARCH_URL + "?" + urllib.parse.urlencode(
            {"q": artist_name, "type": "artist", "limit": self.results_per_query}
        )
        request = urllib.request.Request(
            url, headers={"Authorization": f"Bearer {token}", "User-Agent": USER_AGENT}
        )

        try:
            with urllib.request.urlopen(request, timeout=15) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise StreamingAPIError(
                f"Spotify devolvio HTTP {exc.code} para {artist_name!r}"
            ) from exc
        except (urllib.error.URLError, json.JSONDecodeError, TimeoutError) as exc:
            raise StreamingAPIError(f"Fallo la consulta a Spotify: {exc}") from exc

        identity = parse_search_payload(payload, artist_name)
        logger.info(
            "Identidad de Spotify: %s (%s)", identity["name"], identity["spotify_id"]
        )
        return identity
