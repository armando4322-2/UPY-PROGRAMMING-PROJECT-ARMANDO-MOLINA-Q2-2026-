"""Tests del motor de alertas."""

from folk_analytics.analytics.alerts import AlertLevel, evaluate_alerts
from folk_analytics.analytics.trends import TrendDirection, TrendResult


def trend(change_pct: float, r2: float = 0.9, n: int = 30) -> TrendResult:
    """Construye un TrendResult con la direccion coherente al cambio."""
    if change_pct > 5:
        direction = TrendDirection.GROWING
    elif change_pct < -5:
        direction = TrendDirection.DECLINING
    else:
        direction = TrendDirection.STABLE
    return TrendResult(
        direction=direction,
        change_pct=change_pct,
        slope_per_day=change_pct,
        r_squared=r2,
        sample_size=n,
    )


class TestEvaluateAlerts:
    def test_estabilidad_no_genera_alertas(self):
        assert evaluate_alerts("Test", trend(1.0)) == []

    def test_declive_moderado_genera_aviso(self):
        alerts = evaluate_alerts("Test", trend(-8.0))
        assert any(a.level is AlertLevel.WARNING for a in alerts)

    def test_caida_pronunciada_genera_alerta_critica(self):
        alerts = evaluate_alerts("Test", trend(-25.0))
        assert any(a.level is AlertLevel.CRITICAL for a in alerts)

    def test_caida_critica_no_duplica_el_aviso(self):
        alerts = evaluate_alerts("Test", trend(-25.0))
        assert sum(a.level is AlertLevel.WARNING for a in alerts) == 0

    def test_crecimiento_excepcional_se_informa(self):
        alerts = evaluate_alerts("Test", trend(40.0))
        assert any("excepcional" in a.message for a in alerts)

    def test_sin_actividad_avisa_y_corta(self):
        alerts = evaluate_alerts("Test", trend(0.0), has_activity=False)
        assert len(alerts) == 1
        assert alerts[0].level is AlertLevel.WARNING

    def test_datos_insuficientes_solo_informa(self):
        insuficiente = TrendResult(
            direction=TrendDirection.INSUFFICIENT_DATA,
            change_pct=0.0,
            slope_per_day=0.0,
            r_squared=0.0,
            sample_size=2,
        )
        alerts = evaluate_alerts("Test", insuficiente)
        assert len(alerts) == 1
        assert alerts[0].level is AlertLevel.INFO

    def test_serie_ruidosa_se_marca(self):
        alerts = evaluate_alerts("Test", trend(1.0, r2=0.05))
        assert any("ruidosa" in a.message for a in alerts)

    def test_umbral_exacto_de_caida_dispara_critico(self):
        alerts = evaluate_alerts("Test", trend(-15.0))
        assert any(a.level is AlertLevel.CRITICAL for a in alerts)
