"""Motor de alertas.

Es la parte del agente que permite pasar de 'consulto cuando me acuerdo'
a 'el sistema me avisa'. Evalua el resultado del analisis contra los
umbrales configurados y produce alertas accionables.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from folk_analytics import config
from folk_analytics.analytics.trends import TrendDirection, TrendResult
from folk_analytics.logging_setup import get_logger

logger = get_logger("analytics.alerts")


class AlertLevel(Enum):
    """Severidad de una alerta."""

    INFO = "INFO"
    WARNING = "AVISO"
    CRITICAL = "CRITICO"


@dataclass(frozen=True)
class Alert:
    """Aviso generado por el agente sobre un artista."""

    level: AlertLevel
    artist_name: str
    message: str
    metric: str

    def __str__(self) -> str:
        return f"[{self.level.value}] {self.artist_name}: {self.message}"


def evaluate_alerts(
    artist_name: str,
    trend: TrendResult,
    metric: str = "followers",
    has_activity: bool = True,
) -> list[Alert]:
    """Evalua una tendencia y devuelve las alertas que correspondan."""
    alerts: list[Alert] = []

    if not has_activity:
        alerts.append(
            Alert(
                level=AlertLevel.WARNING,
                artist_name=artist_name,
                message="Sin actividad de streaming registrada",
                metric=metric,
            )
        )
        return alerts

    if trend.direction is TrendDirection.INSUFFICIENT_DATA:
        alerts.append(
            Alert(
                level=AlertLevel.INFO,
                artist_name=artist_name,
                message=(
                    f"Historico insuficiente para un analisis fiable "
                    f"({trend.sample_size} de {config.MIN_SNAPSHOTS_FOR_TREND} puntos)"
                ),
                metric=metric,
            )
        )
        return alerts

    if trend.change_pct <= config.ALERT_DROP_PCT:
        alerts.append(
            Alert(
                level=AlertLevel.CRITICAL,
                artist_name=artist_name,
                message=(
                    f"Caida pronunciada de {metric}: {trend.change_pct:+.1f}% "
                    f"en la ventana analizada"
                ),
                metric=metric,
            )
        )
    elif trend.direction is TrendDirection.DECLINING:
        alerts.append(
            Alert(
                level=AlertLevel.WARNING,
                artist_name=artist_name,
                message=f"Tendencia a la baja: {trend.change_pct:+.1f}%",
                metric=metric,
            )
        )

    if trend.change_pct >= config.ALERT_SPIKE_PCT:
        alerts.append(
            Alert(
                level=AlertLevel.INFO,
                artist_name=artist_name,
                message=(
                    f"Crecimiento excepcional de {metric}: {trend.change_pct:+.1f}%"
                ),
                metric=metric,
            )
        )

    if not trend.is_reliable and trend.direction is not TrendDirection.INSUFFICIENT_DATA:
        alerts.append(
            Alert(
                level=AlertLevel.INFO,
                artist_name=artist_name,
                message=(
                    f"Serie ruidosa: la tendencia tiene confianza "
                    f"{trend.confidence_label} (R2={trend.r_squared:.2f})"
                ),
                metric=metric,
            )
        )

    for alert in alerts:
        logger.info("Alerta generada -> %s", alert)

    return alerts
