"""Metricas descriptivas sobre el historico de un artista."""

from __future__ import annotations

from dataclasses import dataclass
from statistics import mean, median, pstdev

from folk_analytics.api.models import ArtistData
from folk_analytics.logging_setup import get_logger

logger = get_logger("analytics.metrics")


@dataclass(frozen=True)
class MetricsSummary:
    """Resumen estadistico de una serie de instantaneas."""

    sample_size: int
    first_value: float
    last_value: float
    minimum: float
    maximum: float
    average: float
    median_value: float
    std_dev: float
    net_change: float
    net_change_pct: float
    avg_daily_change: float
    span_days: int

    @property
    def is_empty(self) -> bool:
        return self.sample_size == 0


def _empty_summary() -> MetricsSummary:
    return MetricsSummary(
        sample_size=0,
        first_value=0.0,
        last_value=0.0,
        minimum=0.0,
        maximum=0.0,
        average=0.0,
        median_value=0.0,
        std_dev=0.0,
        net_change=0.0,
        net_change_pct=0.0,
        avg_daily_change=0.0,
        span_days=0,
    )


def summarize(history: list[ArtistData], metric: str = "followers") -> MetricsSummary:
    """Calcula el resumen estadistico de una metrica en el historico.

    Args:
        history: instantaneas ordenadas cronologicamente.
        metric : nombre del atributo numerico a resumir.
    """
    if not history:
        logger.warning("Se pidio un resumen sobre un historico vacio")
        return _empty_summary()

    values = [float(getattr(snapshot, metric)) for snapshot in history]

    span_days = max(1, (history[-1].captured_at - history[0].captured_at).days)
    net_change = values[-1] - values[0]
    net_change_pct = (net_change / values[0] * 100) if values[0] else 0.0

    summary = MetricsSummary(
        sample_size=len(values),
        first_value=values[0],
        last_value=values[-1],
        minimum=min(values),
        maximum=max(values),
        average=mean(values),
        median_value=median(values),
        std_dev=pstdev(values) if len(values) > 1 else 0.0,
        net_change=net_change,
        net_change_pct=net_change_pct,
        avg_daily_change=net_change / span_days,
        span_days=span_days,
    )

    logger.debug(
        "Resumen de '%s': n=%d, media=%.0f, cambio neto=%+.0f (%.1f%%)",
        metric,
        summary.sample_size,
        summary.average,
        summary.net_change,
        summary.net_change_pct,
    )
    return summary


def estimate_daily_plays(monthly_listeners: int, window_days: int = 30) -> float:
    """Estimacion sencilla de reproducciones diarias.

    Es una aproximacion declarada, no un dato de la plataforma: reparte
    los oyentes mensuales entre los dias de la ventana.
    """
    if window_days <= 0:
        raise ValueError("La ventana debe ser de al menos un dia")
    return monthly_listeners / window_days
