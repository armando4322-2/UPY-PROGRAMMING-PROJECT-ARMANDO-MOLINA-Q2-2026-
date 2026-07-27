"""Deteccion de tendencias sobre series temporales reales.

Se combinan dos senales complementarias:

1. **Cambio porcentual** entre la media de la primera mitad de la ventana
   y la media de la segunda mitad. Es intuitivo y facil de explicar.
2. **Pendiente por regresion lineal** (minimos cuadrados) sobre todos los
   puntos. Es mas robusta frente a valores atipicos en los extremos.

La direccion final se decide por el cambio porcentual; la pendiente y el
coeficiente de determinacion (R^2) se reportan como medida de confianza.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from folk_analytics import config
from folk_analytics.api.models import ArtistData
from folk_analytics.logging_setup import get_logger

logger = get_logger("analytics.trends")


class TrendDirection(Enum):
    """Direccion detectada en una serie."""

    GROWING = "CRECIENDO"
    DECLINING = "DECAYENDO"
    STABLE = "ESTABLE"
    INSUFFICIENT_DATA = "DATOS INSUFICIENTES"


@dataclass(frozen=True)
class TrendResult:
    """Resultado del analisis de tendencia."""

    direction: TrendDirection
    change_pct: float
    slope_per_day: float
    r_squared: float
    sample_size: int

    @property
    def is_reliable(self) -> bool:
        """True si hay suficientes puntos y el ajuste lineal es decente."""
        return (
            self.sample_size >= config.MIN_SNAPSHOTS_FOR_TREND
            and self.r_squared >= 0.30
        )

    @property
    def confidence_label(self) -> str:
        """Etiqueta legible del nivel de confianza."""
        if self.sample_size < config.MIN_SNAPSHOTS_FOR_TREND:
            return "insuficiente"
        if self.r_squared >= 0.70:
            return "alta"
        if self.r_squared >= 0.30:
            return "media"
        return "baja"


def _linear_regression(values: list[float]) -> tuple[float, float]:
    """Ajusta y = a + b*x por minimos cuadrados sobre indices 0..n-1.

    Returns:
        (pendiente, r_cuadrado)
    """
    n = len(values)
    if n < 2:
        return 0.0, 0.0

    xs = list(range(n))
    mean_x = sum(xs) / n
    mean_y = sum(values) / n

    sxy = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, values))
    sxx = sum((x - mean_x) ** 2 for x in xs)
    syy = sum((y - mean_y) ** 2 for y in values)

    if sxx == 0:
        return 0.0, 0.0

    slope = sxy / sxx
    r_squared = (sxy ** 2) / (sxx * syy) if syy > 0 else 0.0
    return slope, r_squared


def _split_halves(values: list[float]) -> tuple[list[float], list[float]]:
    """Divide una serie en dos mitades.

    Con un numero impar de elementos se descarta el punto central, en
    lugar de asumir que la longitud es par como hacia la version anterior
    del proyecto.
    """
    n = len(values)
    half = n // 2
    return values[:half], values[n - half:]


def analyze_trend(values: list[float]) -> TrendResult:
    """Analiza la tendencia de una serie de valores ordenada en el tiempo."""
    n = len(values)

    if n < config.MIN_SNAPSHOTS_FOR_TREND:
        logger.warning(
            "Solo hay %d puntos; se requieren %d para calcular una tendencia",
            n,
            config.MIN_SNAPSHOTS_FOR_TREND,
        )
        return TrendResult(
            direction=TrendDirection.INSUFFICIENT_DATA,
            change_pct=0.0,
            slope_per_day=0.0,
            r_squared=0.0,
            sample_size=n,
        )

    first_half, second_half = _split_halves(values)
    mean_first = sum(first_half) / len(first_half)
    mean_second = sum(second_half) / len(second_half)

    change_pct = ((mean_second - mean_first) / mean_first * 100) if mean_first else 0.0
    slope, r_squared = _linear_regression(values)

    if change_pct > config.TREND_THRESHOLD_PCT:
        direction = TrendDirection.GROWING
    elif change_pct < -config.TREND_THRESHOLD_PCT:
        direction = TrendDirection.DECLINING
    else:
        direction = TrendDirection.STABLE

    logger.info(
        "Tendencia detectada: %s (%+.1f%%, pendiente %+.1f/dia, R2=%.2f, n=%d)",
        direction.value,
        change_pct,
        slope,
        r_squared,
        n,
    )

    return TrendResult(
        direction=direction,
        change_pct=change_pct,
        slope_per_day=slope,
        r_squared=r_squared,
        sample_size=n,
    )


def analyze_artist_trend(history: list[ArtistData], metric: str = "followers") -> TrendResult:
    """Analiza la tendencia de una metrica concreta en el historico.

    Args:
        history: instantaneas ordenadas cronologicamente.
        metric : 'followers', 'monthly_listeners' o 'popularity'.
    """
    if metric not in ("followers", "monthly_listeners", "popularity"):
        raise ValueError(f"Metrica no soportada: {metric!r}")

    values = [float(getattr(snapshot, metric)) for snapshot in history]
    return analyze_trend(values)
