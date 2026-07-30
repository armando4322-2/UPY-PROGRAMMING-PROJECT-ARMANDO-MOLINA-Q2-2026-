"""Reportes en consola.

Todo el arte ASCII/Unicode vive aqui. Si la terminal no soporta Unicode
se degrada automaticamente a caracteres ASCII en vez de lanzar
`UnicodeEncodeError`, que era el fallo tipico en cmd.exe de Windows.
"""

from __future__ import annotations

from folk_analytics.analytics.alerts import Alert, AlertLevel
from folk_analytics.analytics.metrics import MetricsSummary
from folk_analytics.analytics.trends import TrendDirection, TrendResult
from folk_analytics.api.models import ArtistData, Track
from folk_analytics.logging_setup import CONSOLE_UNICODE

WIDTH = 62

# Juegos de caracteres segun soporte de la terminal.
if CONSOLE_UNICODE:
    HEAVY, LIGHT = "═", "─"
    ARROWS = {
        TrendDirection.GROWING: "↗ CRECIENDO",
        TrendDirection.DECLINING: "↘ DECAYENDO",
        TrendDirection.STABLE: "→ ESTABLE",
        TrendDirection.INSUFFICIENT_DATA: "? DATOS INSUFICIENTES",
    }
    SPARK_CHARS = "▁▂▃▄▅▆▇█"
else:
    HEAVY, LIGHT = "=", "-"
    ARROWS = {
        TrendDirection.GROWING: "^ CRECIENDO",
        TrendDirection.DECLINING: "v DECAYENDO",
        TrendDirection.STABLE: "> ESTABLE",
        TrendDirection.INSUFFICIENT_DATA: "? DATOS INSUFICIENTES",
    }
    SPARK_CHARS = ".:-=+*#@"

ALERT_MARKS = {
    AlertLevel.INFO: "[i]",
    AlertLevel.WARNING: "[!]",
    AlertLevel.CRITICAL: "[X]",
}


def _line(char: str) -> str:
    return char * WIDTH


def _field(label: str, value: str) -> str:
    return f"  {label:<22}: {value}"


def _metric_field(snapshot: ArtistData, label: str, metric: str, suffix: str = "") -> str:
    """Formatea una metrica distinguiendo el cero real del dato no publicado.

    Mostrar "0" cuando la fuente simplemente no publica el dato afirmaria
    algo falso sobre el artista. Cada fuente declara que metricas no expone
    y aqui se refleja tal cual.
    """
    if not snapshot.is_available(metric):
        return _field(label, "no publicado por esta fuente")
    return _field(label, f"{getattr(snapshot, metric):,}{suffix}")


def render_sparkline(values: list[float], width: int = 30) -> str:
    """Dibuja una mini-grafica de una linea con la serie de valores."""
    if not values:
        return "(sin datos)"
    if len(values) == 1:
        return SPARK_CHARS[len(SPARK_CHARS) // 2]

    # Remuestrea a `width` puntos si la serie es mas larga.
    if len(values) > width:
        step = len(values) / width
        sampled = [values[int(i * step)] for i in range(width)]
    else:
        sampled = values

    low, high = min(sampled), max(sampled)
    span = high - low

    if span == 0:
        return SPARK_CHARS[len(SPARK_CHARS) // 2] * len(sampled)

    scale = len(SPARK_CHARS) - 1
    return "".join(
        SPARK_CHARS[int((value - low) / span * scale)] for value in sampled
    )


def render_report(
    session_id: str,
    snapshot: ArtistData,
    summary: MetricsSummary,
    trend: TrendResult,
    alerts: list[Alert],
    history_values: list[float] | None = None,
    metric: str = "followers",
    tracks: tuple[Track, ...] = (),
) -> str:
    """Construye el reporte completo de un artista como texto."""
    lines: list[str] = []

    lines.append("")
    lines.append(_line(HEAVY))
    lines.append(f"  FOLK ANALYTICS  |  SESION {session_id}")
    lines.append(_line(HEAVY))

    lines.append("  IDENTIDAD")
    lines.append(_field("Artista", snapshot.name))
    lines.append(_field("ID", snapshot.artist_id))
    lines.append(_field("Fuente de datos", snapshot.source))
    lines.append(_field("Capturado", snapshot.captured_at.strftime("%Y-%m-%d %H:%M UTC")))

    lines.append(_line(LIGHT))
    lines.append("  METRICAS ACTUALES")
    lines.append(_metric_field(snapshot, "Seguidores", "followers"))
    lines.append(_metric_field(snapshot, "Oyentes mensuales", "monthly_listeners"))
    lines.append(_metric_field(snapshot, "Popularidad", "popularity", suffix="/100"))
    if snapshot.albums:
        lines.append(_field("Albumes publicados", f"{snapshot.albums:,}"))

    lines.append(_line(LIGHT))
    lines.append(f"  HISTORICO ({metric})")
    if summary.is_empty:
        lines.append(_field("Estado", "sin historico"))
    else:
        lines.append(_field("Instantaneas", f"{summary.sample_size}"))
        lines.append(_field("Periodo cubierto", f"{summary.span_days} dias"))
        lines.append(_field("Media", f"{summary.average:,.0f}"))
        lines.append(_field("Minimo / Maximo", f"{summary.minimum:,.0f} / {summary.maximum:,.0f}"))
        lines.append(_field("Desviacion estandar", f"{summary.std_dev:,.0f}"))
        lines.append(_field("Cambio neto", f"{summary.net_change:+,.0f} ({summary.net_change_pct:+.1f}%)"))
        lines.append(_field("Cambio medio diario", f"{summary.avg_daily_change:+,.0f}/dia"))

    if history_values:
        lines.append(_field("Evolucion", render_sparkline(history_values)))

    lines.append(_line(LIGHT))
    lines.append("  TENDENCIA")
    lines.append(_field("Direccion", ARROWS[trend.direction]))
    if trend.direction is not TrendDirection.INSUFFICIENT_DATA:
        lines.append(_field("Cambio en la ventana", f"{trend.change_pct:+.1f}%"))
        lines.append(_field("Pendiente", f"{trend.slope_per_day:+,.0f} por instantanea"))
        lines.append(_field("Confianza", f"{trend.confidence_label} (R2={trend.r_squared:.2f})"))
    lines.append(_field("Puntos analizados", f"{trend.sample_size}"))

    lines.append(_line(LIGHT))
    lines.append("  ALERTAS")
    if not alerts:
        lines.append(_field("Estado", "sin alertas"))
    else:
        for alert in alerts:
            mark = ALERT_MARKS[alert.level]
            lines.append(f"  {mark} {alert.message}")

    if tracks:
        lines.append(_line(LIGHT))
        lines.append(f"  TOP {len(tracks)} CANCIONES")
        lines.append(f"  {'#':<3}{'TITULO':<34}{'ALBUM':<24}{'DURA':>6}")
        for track in tracks:
            title = track.title[:32] + ("…" if len(track.title) > 32 else "")
            album = track.album[:22] + ("…" if len(track.album) > 22 else "")
            lines.append(f"  {track.position:<3}{title:<34}{album:<24}{track.duration:>6}")
        lines.append("  (ordenadas por el indice de popularidad de la fuente,")
        lines.append("   que no es un numero de reproducciones)")

    lines.append(_line(HEAVY))
    lines.append("")

    return "\n".join(lines)


def render_summary_table(rows: list[dict]) -> str:
    """Tabla comparativa de varios artistas.

    Args:
        rows: diccionarios con las claves `name`, `followers`, `change_pct`
              y `direction`.
    """
    if not rows:
        return "\n  No hay artistas que mostrar.\n"

    lines: list[str] = ["", _line(HEAVY), "  RESUMEN COMPARATIVO", _line(HEAVY)]
    lines.append(f"  {'ARTISTA':<24}{'SEGUIDORES':>14}{'CAMBIO':>10}  TENDENCIA")
    lines.append(_line(LIGHT))

    ordered = sorted(rows, key=lambda r: r.get("change_pct", 0.0), reverse=True)
    for row in ordered:
        name = str(row["name"])[:23]
        followers = f"{row['followers']:,}"
        change = f"{row['change_pct']:+.1f}%"
        direction = ARROWS[row["direction"]].split(" ", 1)[-1]
        lines.append(f"  {name:<24}{followers:>14}{change:>10}  {direction}")

    lines.append(_line(HEAVY))
    lines.append("")
    return "\n".join(lines)
