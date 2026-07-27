"""Cliente de datos simulados.

A diferencia de un `random` puro, este cliente genera una serie temporal
*coherente*: para un artista y una fecha dados siempre devuelve el mismo
valor. Eso permite reconstruir historicos crebles y, sobre todo, hace que
las tendencias detectadas signifiquen algo en lugar de medir ruido.

El modelo es simple pero honesto:

    valor(dia) = base * (1 + tasa_crecimiento) ** dias_desde_hoy * ruido(dia)

donde `ruido(dia)` es un factor deterministico derivado del identificador
del artista y de la fecha del calendario.
"""

from __future__ import annotations

import random
import time
from datetime import date, datetime, timedelta, timezone

from folk_analytics import config
from folk_analytics.api.base import (
    ArtistNotFoundError,
    StreamingAPIError,
    StreamingClient,
)
from folk_analytics.api.models import ArtistData, utcnow
from folk_analytics.logging_setup import get_logger

logger = get_logger("api.simulated")


# Catalogo simulado. `daily_growth` es la tasa de crecimiento diaria
# compuesta y `volatility` la amplitud del ruido aleatorio diario.
ARTIST_DB: dict[str, dict] = {
    "aurora": {
        "artist_id": "ART-001",
        "display_name": "AURORA",
        "followers": 2_400_000,
        "monthly_listeners": 1_800_000,
        "popularity": 74,
        "daily_growth": 0.0021,
        "volatility": 0.06,
    },
    "iron & wine": {
        "artist_id": "ART-002",
        "display_name": "Iron & Wine",
        "followers": 890_000,
        "monthly_listeners": 620_000,
        "popularity": 58,
        "daily_growth": 0.0003,
        "volatility": 0.04,
    },
    "sufjan stevens": {
        "artist_id": "ART-003",
        "display_name": "Sufjan Stevens",
        "followers": 3_100_000,
        "monthly_listeners": 2_250_000,
        "popularity": 69,
        "daily_growth": 0.0009,
        "volatility": 0.05,
    },
    "novo amor": {
        "artist_id": "ART-004",
        "display_name": "Novo Amor",
        "followers": 1_050_000,
        "monthly_listeners": 780_000,
        "popularity": 61,
        "daily_growth": 0.0034,
        "volatility": 0.08,
    },
    "the paper kites": {
        "artist_id": "ART-005",
        "display_name": "The Paper Kites",
        "followers": 1_420_000,
        "monthly_listeners": 1_130_000,
        "popularity": 64,
        "daily_growth": -0.0075,
        "volatility": 0.04,
    },
    "vashti bunyan": {
        "artist_id": "ART-006",
        "display_name": "Vashti Bunyan",
        "followers": 118_000,
        "monthly_listeners": 74_000,
        "popularity": 41,
        "daily_growth": -0.0009,
        "volatility": 0.11,
    },
    # Artista ficticio: sirve para ejercitar la alerta critica sin
    # atribuir cifras inventadas de derrumbe a un artista real.
    "hollow pines": {
        "artist_id": "ART-007",
        "display_name": "Hollow Pines",
        "followers": 46_000,
        "monthly_listeners": 31_000,
        "popularity": 28,
        "daily_growth": -0.018,
        "volatility": 0.05,
    },
    "unknown artist": {
        "artist_id": "ART-999",
        "display_name": "Unknown Artist",
        "followers": 0,
        "monthly_listeners": 0,
        "popularity": 0,
        "daily_growth": 0.0,
        "volatility": 0.0,
    },
}


class SimulatedClient(StreamingClient):
    """Fuente de datos sintetica, deterministica y sin dependencias de red."""

    source_name = "simulated"

    def __init__(self, failure_rate: float = 0.12, sleep_between_retries: bool = True):
        """
        Args:
            failure_rate: probabilidad de que una llamada falle de forma
                transitoria, para ejercitar la logica de reintentos.
            sleep_between_retries: si es False no se duerme entre reintentos
                (util en los tests).
        """
        self.failure_rate = failure_rate
        self.sleep_between_retries = sleep_between_retries
        self._rng = random.Random()

    # -- Modelo de datos ------------------------------------------------------

    @staticmethod
    def _noise_factor(artist_id: str, day: date, volatility: float) -> float:
        """Factor de ruido deterministico para un artista en una fecha dada."""
        if volatility <= 0:
            return 1.0
        seeded = random.Random(f"{artist_id}:{day.isoformat()}")
        return 1.0 + seeded.uniform(-volatility, volatility)

    def _metrics_for_day(self, entry: dict, target_day: date) -> tuple[int, int]:
        """Calcula (followers, monthly_listeners) para una fecha concreta.

        Los valores base del catalogo representan el dia de hoy; las fechas
        pasadas se extrapolan hacia atras con la tasa de crecimiento.
        """
        today = datetime.now(timezone.utc).date()
        days_offset = (target_day - today).days

        growth = (1.0 + entry["daily_growth"]) ** days_offset
        noise = self._noise_factor(entry["artist_id"], target_day, entry["volatility"])

        followers = max(0, int(entry["followers"] * growth * noise))
        listeners = max(0, int(entry["monthly_listeners"] * growth * noise))
        return followers, listeners

    # -- Interfaz publica -----------------------------------------------------

    def available_artists(self) -> list[str]:
        """Nombres de todos los artistas del catalogo simulado."""
        return [entry["display_name"] for entry in ARTIST_DB.values()]

    def fetch_artist(self, artist_name: str) -> ArtistData:
        """Recupera las metricas de hoy para un artista, con reintentos."""
        return self.fetch_artist_at(artist_name, datetime.now(timezone.utc).date())

    def fetch_artist_at(self, artist_name: str, target_day: date) -> ArtistData:
        """Igual que `fetch_artist` pero para una fecha arbitraria.

        Se usa para reconstruir historicos al arrancar el agente por
        primera vez.
        """
        key = artist_name.strip().lower()
        entry = ARTIST_DB.get(key)

        if entry is None:
            logger.error("Artista '%s' no encontrado en el catalogo", artist_name)
            raise ArtistNotFoundError(f"Artista no encontrado: {artist_name!r}")

        logger.debug("Consultando '%s' para la fecha %s", artist_name, target_day)
        self._simulate_network(artist_name)

        followers, listeners = self._metrics_for_day(entry, target_day)

        captured = datetime.combine(
            target_day, datetime.min.time(), tzinfo=timezone.utc
        )
        if target_day == datetime.now(timezone.utc).date():
            captured = utcnow()

        data = ArtistData(
            artist_id=entry["artist_id"],
            name=entry["display_name"],
            followers=followers,
            monthly_listeners=listeners,
            popularity=entry["popularity"],
            source=self.source_name,
            captured_at=captured,
        )

        if not data.has_activity:
            logger.warning(
                "El artista '%s' no registra actividad de streaming", data.name
            )

        logger.info(
            "Respuesta recibida para '%s' (ID: %s, seguidores: %s)",
            data.name,
            data.artist_id,
            f"{data.followers:,}",
        )
        return data

    # -- Simulacion de red ----------------------------------------------------

    def _simulate_network(self, artist_name: str) -> None:
        """Simula fallos transitorios y reintenta de verdad.

        La version anterior del proyecto registraba 'reintentando...' pero
        no reintentaba nada. Aqui el reintento existe: si se agotan los
        intentos, la llamada falla con `StreamingAPIError`.
        """
        for attempt in range(1, config.API_MAX_RETRIES + 1):
            if self._rng.random() >= self.failure_rate:
                if attempt > 1:
                    logger.info(
                        "Consulta de '%s' resuelta en el intento %d", artist_name, attempt
                    )
                return

            logger.warning(
                "Fallo transitorio consultando '%s' (intento %d de %d)",
                artist_name,
                attempt,
                config.API_MAX_RETRIES,
            )
            if self.sleep_between_retries and attempt < config.API_MAX_RETRIES:
                time.sleep(config.API_RETRY_BACKOFF_SECONDS * attempt)

        logger.error(
            "Se agotaron los %d intentos para '%s'", config.API_MAX_RETRIES, artist_name
        )
        raise StreamingAPIError(
            f"La fuente no respondio tras {config.API_MAX_RETRIES} intentos: {artist_name!r}"
        )
