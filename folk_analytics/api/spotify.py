"""Cliente de la API real de Spotify (Client Credentials Flow).

ESTADO: SIN VERIFICAR CONTRA LA API REAL
----------------------------------------
Este modulo esta escrito pero **nunca se ha ejecutado contra Spotify**,
porque el proyecto no dispone de credenciales. Lo unico probado es que
degrada correctamente a la fuente simulada cuando faltan.

En concreto, la forma exacta de la respuesta de busqueda esta tomada de la
documentacion de Spotify, no capturada de una llamada real. Los tests de
`tests/test_spotify.py` validan *nuestra* logica de seleccion y conversion
sobre esa forma supuesta; no demuestran que la suposicion sea correcta.

Para datos reales verificados y sin credenciales, usa `DeezerClient`.

Requiere `requests` y credenciales en variables de entorno o en un
archivo `.env` (ver `.env.example`).

NOTA IMPORTANTE SOBRE LOS DATOS
--------------------------------
La API publica de Spotify **no expone oyentes mensuales**. Ese dato solo
aparece en la interfaz web del artista. Por tanto este cliente devuelve
`monthly_listeners = 0` y el analisis se apoya en `followers` y en el
indice `popularity` (0-100), que si estan disponibles oficialmente.
Documentarlo es preferible a inventar el numero.
"""

from __future__ import annotations

import os
import time

from folk_analytics import config
from folk_analytics.api.base import (
    ArtistNotFoundError,
    StreamingAPIError,
    StreamingClient,
)
from folk_analytics.api.matching import select_best_match
from folk_analytics.api.models import ArtistData, utcnow
from folk_analytics.logging_setup import get_logger

logger = get_logger("api.spotify")


def _load_dotenv_if_present() -> None:
    """Carga el archivo .env si existe y si python-dotenv esta instalado."""
    env_path = config.PROJECT_ROOT / ".env"
    if not env_path.exists():
        return
    try:
        from dotenv import load_dotenv

        load_dotenv(env_path)
        logger.debug("Credenciales cargadas desde .env")
    except ImportError:
        # Fallback minimo sin dependencias externas.
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())
        logger.debug("Credenciales cargadas desde .env (parser interno)")


def to_artist_data(record: dict) -> ArtistData:
    """Convierte un objeto artista de Spotify en un `ArtistData`."""
    return ArtistData(
        artist_id=record["id"],
        name=record.get("name", "").strip() or "Desconocido",
        followers=int((record.get("followers") or {}).get("total", 0) or 0),
        monthly_listeners=0,  # no publicado por la API de Spotify
        popularity=int(record.get("popularity", 0) or 0),
        source="spotify",
        captured_at=utcnow(),
        unavailable_metrics=("monthly_listeners",),
    )


def parse_search_payload(payload: dict, query: str) -> ArtistData:
    """Interpreta la respuesta de busqueda y elige el artista correcto.

    Se mantiene independiente del transporte para poder probarla sin red y
    sin credenciales. Aplica la misma desambiguacion que el cliente de
    Deezer: sin ella, buscar un nombre compartido por varios artistas
    devolveria el primero que Spotify decida listar.
    """
    if not isinstance(payload, dict):
        raise StreamingAPIError("Spotify devolvio una respuesta con formato inesperado")

    if "error" in payload and payload["error"]:
        error = payload["error"]
        message = error.get("message", "error desconocido") if isinstance(error, dict) else str(error)
        raise StreamingAPIError(f"Spotify respondio con un error: {message}")

    items = (payload.get("artists") or {}).get("items") or []
    best = select_best_match(
        items,
        query,
        name_of=lambda c: c.get("name", ""),
        rank_of=lambda c: (c.get("followers") or {}).get("total", 0),
        source="Spotify",
    )
    return to_artist_data(best)


class SpotifyClient(StreamingClient):
    """Cliente contra la API oficial de Spotify."""

    source_name = "spotify"

    def __init__(
        self,
        client_id: str | None = None,
        client_secret: str | None = None,
        results_per_query: int = 10,
    ):
        """
        Args:
            results_per_query: cuantos candidatos pedir. Con uno solo la
                desambiguacion es imposible y se acaba analizando al artista
                equivocado sin enterarse.
        """
        _load_dotenv_if_present()
        self.results_per_query = results_per_query

        self.client_id = client_id or os.environ.get("SPOTIFY_CLIENT_ID", "")
        self.client_secret = client_secret or os.environ.get("SPOTIFY_CLIENT_SECRET", "")

        if not self.client_id or not self.client_secret:
            raise StreamingAPIError(
                "Faltan credenciales de Spotify. Copia .env.example a .env y "
                "rellena SPOTIFY_CLIENT_ID y SPOTIFY_CLIENT_SECRET. "
                "Se obtienen en https://developer.spotify.com/dashboard"
            )

        try:
            import requests  # noqa: F401
        except ImportError as exc:
            raise StreamingAPIError(
                "Falta la libreria 'requests'. Instalala con: "
                "pip install -r requirements.txt"
            ) from exc

        self._token: str | None = None
        self._token_expires_at: float = 0.0

    # -- Autenticacion --------------------------------------------------------

    def _get_token(self) -> str:
        """Obtiene (y cachea) un token de acceso de aplicacion."""
        import requests

        if self._token and time.time() < self._token_expires_at - 60:
            return self._token

        logger.debug("Solicitando token de acceso a Spotify")
        try:
            response = requests.post(
                config.SPOTIFY_TOKEN_URL,
                data={"grant_type": "client_credentials"},
                auth=(self.client_id, self.client_secret),
                timeout=10,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            logger.error("Fallo la autenticacion con Spotify: %s", exc)
            raise StreamingAPIError(f"No se pudo autenticar con Spotify: {exc}") from exc

        payload = response.json()
        self._token = payload["access_token"]
        self._token_expires_at = time.time() + payload.get("expires_in", 3600)
        logger.info("Token de Spotify obtenido correctamente")
        return self._token

    # -- Interfaz publica -----------------------------------------------------

    def available_artists(self) -> list[str]:
        """La API real no permite enumerar el catalogo completo."""
        return []

    def fetch_artist(self, artist_name: str) -> ArtistData:
        """Busca un artista por nombre y devuelve sus metricas actuales."""
        import requests

        token = self._get_token()
        logger.info("Consultando la API de Spotify para '%s'", artist_name)

        try:
            response = requests.get(
                f"{config.SPOTIFY_API_BASE}/search",
                headers={"Authorization": f"Bearer {token}"},
                params={
                    "q": artist_name,
                    "type": "artist",
                    "limit": self.results_per_query,
                },
                timeout=10,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            logger.error("Fallo la consulta a Spotify: %s", exc)
            raise StreamingAPIError(f"Fallo la consulta a Spotify: {exc}") from exc

        data = parse_search_payload(response.json(), artist_name)

        logger.info(
            "Datos reales recibidos: %s (ID: %s, seguidores: %s, popularidad: %d)",
            data.name,
            data.artist_id,
            f"{data.followers:,}",
            data.popularity,
        )
        return data
