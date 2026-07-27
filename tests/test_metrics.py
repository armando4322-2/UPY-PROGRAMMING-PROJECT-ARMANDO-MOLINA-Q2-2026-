"""Tests de metricas descriptivas."""

import pytest

from folk_analytics.analytics.metrics import estimate_daily_plays, summarize
from tests.conftest import make_snapshot


class TestSummarize:
    def test_historico_vacio_devuelve_resumen_vacio(self):
        resumen = summarize([])
        assert resumen.is_empty
        assert resumen.sample_size == 0

    def test_calcula_estadisticos_basicos(self):
        history = [make_snapshot(v, days_ago=d) for d, v in enumerate([400, 300, 200, 100])]
        history.reverse()  # orden cronologico: 100, 200, 300, 400
        resumen = summarize(history)
        assert resumen.sample_size == 4
        assert resumen.minimum == 100
        assert resumen.maximum == 400
        assert resumen.average == 250

    def test_cambio_neto_va_del_primero_al_ultimo(self):
        history = [make_snapshot(100, days_ago=3), make_snapshot(150, days_ago=0)]
        resumen = summarize(history)
        assert resumen.net_change == 50
        assert resumen.net_change_pct == pytest.approx(50.0)

    def test_valor_inicial_cero_no_divide_entre_cero(self):
        history = [make_snapshot(0, days_ago=3), make_snapshot(100, days_ago=0)]
        assert summarize(history).net_change_pct == 0.0

    def test_un_solo_punto_tiene_desviacion_cero(self):
        assert summarize([make_snapshot(100)]).std_dev == 0.0


class TestEstimateDailyPlays:
    def test_reparte_entre_los_dias(self):
        assert estimate_daily_plays(3000, window_days=30) == 100.0

    def test_ventana_invalida_lanza_error(self):
        with pytest.raises(ValueError):
            estimate_daily_plays(1000, window_days=0)
