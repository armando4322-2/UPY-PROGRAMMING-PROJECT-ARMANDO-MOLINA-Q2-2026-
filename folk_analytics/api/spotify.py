"""Cliente de la API real de Spotify (Client Credentials Flow).

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


class SpotifyClient(StreamingClient):
    """Cliente contra la API oficial de Spotify."""

    source_name = "spotify"

    def __init__(self, client_id: str | None = None, client_secret: str | None = None):
        _load_dotenv_if_present()

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
                params={"q": artist_name, "type": "artist", "limit": 1},
                timeout=10,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            logger.error("Fallo la consulta a Spotify: %s", exc)
            raise StreamingAPIError(f"Fallo la consulta a Spotify: {exc}") from exc

        items = response.json().get("artists", {}).get("items", [])
        if not items:
            logger.error("Spotify no devolvio resultados para '%s'", artist_name)
            raise ArtistNotFoundError(f"Artista no encontrado en Spotify: {artist_name!r}")

        artist = items[0]
        data = ArtistData(
            artist_id=artist["id"],
            name=artist["name"],
            followers=artist.get("followers", {}).get("total", 0),
            monthly_listeners=0,  # no disponible en la API publica
            popularity=artist.get("popularity", 0),
            source=self.source_name,
            captured_at=utcnow(),
        )

        logger.info(
            "Datos reales recibidos: %s (seguidores: %s, popularidad: %d)",
            data.name,
            f"{data.followers:,}",
            data.popularity,
        )
        return data
