"""El agente: percibir -> procesar -> actuar.

Esta clase orquesta todas las piezas. No sabe de que fuente vienen los
datos ni como se dibuja el reporte: recibe un cliente y un almacen, y
coordina el ciclo.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from folk_analytics import config
from folk_analytics.analytics.alerts import Alert, evaluate_alerts
from folk_analytics.analytics.metrics import MetricsSummary, summarize
from folk_analytics.analytics.trends import TrendResult, analyze_artist_trend
from folk_analytics.api.base import (
    ArtistNotFoundError,
    StreamingAPIError,
    StreamingClient,
)
from folk_analytics.api.models import ArtistData
from folk_analytics.api.simulated import SimulatedClient
from folk_analytics.logging_setup import get_logger
from folk_analytics.reports.console import render_report
from folk_analytics.storage.json_store import SnapshotStore

logger = get_logger("agent")


class InvalidInputError(ValueError):
    """La entrada proporcionada por el usuario no es valida."""


@dataclass(frozen=True)
class AnalysisResult:
    """Resultado completo del analisis de un artista."""

    session_id: str
    snapshot: ArtistData
    summary: MetricsSummary
    trend: TrendResult
    alerts: list[Alert]
    history_values: list[float]
    metric: str

    def to_report(self) -> str:
        """Renderiza este resultado como reporte de consola."""
        return render_report(
            session_id=self.session_id,
            snapshot=self.snapshot,
            summary=self.summary,
            trend=self.trend,
            alerts=self.alerts,
            history_values=self.history_values,
            metric=self.metric,
        )


def validate_artist_name(raw: str) -> str:
    """Valida y normaliza el nombre de un artista.

    Raises:
        InvalidInputError: si el nombre esta vacio o es demasiado largo.
    """
    if raw is None:
        raise InvalidInputError("No se recibio ningun nombre de artista")

    cleaned = " ".join(str(raw).split())

    if len(cleaned) < config.MIN_ARTIST_NAME_LENGTH:
        raise InvalidInputError("El nombre del artista no puede estar vacio")

    if len(cleaned) > config.MAX_ARTIST_NAME_LENGTH:
        raise InvalidInputError(
            f"El nombre es demasiado largo ({len(cleaned)} caracteres, "
            f"maximo {config.MAX_ARTIST_NAME_LENGTH})"
        )

    return cleaned


class FolkAnalyticsAgent:
    """Agente de inteligencia de streaming."""

    def __init__(
        self,
        client: StreamingClient | None = None,
        store: SnapshotStore | None = None,
        metric: str = "followers",
    ):
        self.client = client or SimulatedClient()
        self.store = store or SnapshotStore()
        self.metric = metric
        logger.info(
            "Agente inicializado (fuente=%s, metrica=%s, historico=%d instantaneas)",
            self.client.source_name,
            self.metric,
            self.store.total_snapshots(),
        )

    # -- Ciclo del agente -----------------------------------------------------

    def analyze(self, artist_name: str, seed_if_empty: bool = True) -> AnalysisResult:
        """Ejecuta el ciclo completo sobre un artista.

        1. **Percibir**: valida la entrada y consulta la fuente de datos.
        2. **Procesar**: guarda la instantanea y analiza el historico.
        3. **Actuar**  : produce metricas, tendencia y alertas.

        Raises:
            InvalidInputError  : entrada no valida.
            ArtistNotFoundError: el artista no existe en la fuente.
            StreamingAPIError  : fallo de la fuente de datos.
        """
        session_id = uuid.uuid4().hex[:8].upper()
        logger.info("--- Sesion %s | consulta: '%s'", session_id, artist_name)

        # 1. PERCIBIR
        name = validate_artist_name(artist_name)
        snapshot = self.client.fetch_artist(name)

        # 2. PROCESAR
        if seed_if_empty and not self.store.has_history(
            snapshot.artist_id, config.MIN_SNAPSHOTS_FOR_TREND
        ):
            self._seed_history(name, snapshot)

        self.store.add(snapshot)
        history = self.store.history(
            snapshot.artist_id, days=config.ANALYSIS_WINDOW_DAYS
        )

        summary = summarize(history, self.metric)
        trend = analyze_artist_trend(history, self.metric)

        # 3. ACTUAR
        alerts = evaluate_alerts(
            artist_name=snapshot.name,
            trend=trend,
            metric=self.metric,
            has_activity=snapshot.has_activity,
        )

        logger.info("Sesion %s completada correctamente", session_id)

        return AnalysisResult(
            session_id=session_id,
            snapshot=snapshot,
            summary=summary,
            trend=trend,
            alerts=alerts,
            history_values=[float(getattr(s, self.metric)) for s in history],
            metric=self.metric,
        )

    def analyze_many(self, artist_names: list[str]) -> tuple[list[AnalysisResult], list[str]]:
        """Analiza varios artistas y separa exitos de fallos.

        Returns:
            (resultados, mensajes_de_error)
        """
        results: list[AnalysisResult] = []
        errors: list[str] = []

        logger.info("Analisis por lotes iniciado: %d consultas", len(artist_names))

        for name in artist_names:
            try:
                results.append(self.analyze(name))
            except InvalidInputError as exc:
                logger.warning("Entrada rechazada: %s", exc)
                errors.append(f"Entrada no valida ({name!r}): {exc}")
            except ArtistNotFoundError as exc:
                logger.error("Artista no encontrado: %s", exc)
                errors.append(f"No encontrado: {name}")
            except StreamingAPIError as exc:
                logger.error("Fallo de la fuente de datos: %s", exc)
                errors.append(f"Fallo de la fuente ({name}): {exc}")

        logger.info(
            "Analisis por lotes terminado: %d correctos, %d con error",
            len(results),
            len(errors),
        )
        return results, errors

    # -- Reconstruccion de historico -----------------------------------------

    def _seed_history(self, artist_name: str, current: ArtistData) -> None:
        """Reconstruye un historico inicial para un artista nuevo.

        Solo es posible con fuentes que puedan consultar fechas pasadas
        (el cliente simulado). Con la API real no hay historico
        retroactivo: el agente empieza a acumularlo desde su primera
        ejecucion, que es el comportamiento honesto.
        """
        fetch_at = getattr(self.client, "fetch_artist_at", None)
        if fetch_at is None:
            logger.info(
                "La fuente '%s' no permite consultas retroactivas; el historico "
                "se acumulara a partir de ahora",
                self.client.source_name,
            )
            return

        today = datetime.now(timezone.utc).date()
        added = 0

        logger.info(
            "Reconstruyendo historico de '%s' (%d dias)",
            current.name,
            config.ANALYSIS_WINDOW_DAYS,
        )

        for days_ago in range(config.ANALYSIS_WINDOW_DAYS, 0, -1):
            past_day = today - timedelta(days=days_ago)
            try:
                past = fetch_at(artist_name, past_day, quiet=True)
            except StreamingAPIError:
                continue
            if self.store.add(past, save=False):
                added += 1

        self.store.save()
        logger.info("Historico reconstruido: %d instantaneas anadidas", added)

    # -- Utilidades -----------------------------------------------------------

    def catalog(self) -> list[str]:
        """Artistas disponibles en la fuente de datos actual."""
        return self.client.available_artists()

    def reset_history(self) -> None:
        """Borra todo el historico almacenado."""
        self.store.clear()
