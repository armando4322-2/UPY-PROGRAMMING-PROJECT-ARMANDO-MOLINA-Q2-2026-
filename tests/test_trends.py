"""Tests del motor de tendencias."""

from folk_analytics.analytics.trends import (
    TrendDirection,
    _linear_regression,
    _split_halves,
    analyze_trend,
)


class TestSplitHalves:
    def test_longitud_par(self):
        first, second = _split_halves([1, 2, 3, 4])
        assert first == [1, 2] and second == [3, 4]

    def test_longitud_impar_descarta_el_centro(self):
        first, second = _split_halves([1, 2, 3, 4, 5])
        assert first == [1, 2] and second == [4, 5]
        assert len(first) == len(second)

    def test_las_mitades_siempre_miden_lo_mismo(self):
        for n in range(2, 40):
            first, second = _split_halves(list(range(n)))
            assert len(first) == len(second)


class TestLinearRegression:
    def test_recta_perfecta_creciente(self):
        slope, r2 = _linear_regression([0, 10, 20, 30, 40])
        assert slope == 10.0
        assert r2 == 1.0

    def test_recta_perfecta_decreciente(self):
        slope, r2 = _linear_regression([40, 30, 20, 10, 0])
        assert slope == -10.0
        assert r2 == 1.0

    def test_serie_constante_no_divide_entre_cero(self):
        slope, r2 = _linear_regression([5, 5, 5, 5])
        assert slope == 0.0 and r2 == 0.0

    def test_serie_de_un_solo_punto(self):
        assert _linear_regression([7]) == (0.0, 0.0)


class TestAnalyzeTrend:
    def test_detecta_crecimiento(self):
        result = analyze_trend([100, 110, 130, 150, 170, 190])
        assert result.direction is TrendDirection.GROWING
        assert result.change_pct > 0

    def test_detecta_declive(self):
        result = analyze_trend([190, 170, 150, 130, 110, 100])
        assert result.direction is TrendDirection.DECLINING
        assert result.change_pct < 0

    def test_detecta_estabilidad(self):
        result = analyze_trend([100, 101, 99, 100, 101, 99])
        assert result.direction is TrendDirection.STABLE
        assert abs(result.change_pct) < 5

    def test_datos_insuficientes(self):
        result = analyze_trend([100, 110])
        assert result.direction is TrendDirection.INSUFFICIENT_DATA
        assert result.sample_size == 2

    def test_serie_de_ceros_no_revienta(self):
        result = analyze_trend([0, 0, 0, 0, 0, 0])
        assert result.change_pct == 0.0
        assert result.direction is TrendDirection.STABLE

    def test_confianza_alta_en_serie_limpia(self):
        result = analyze_trend([100, 120, 140, 160, 180, 200])
        assert result.r_squared > 0.9
        assert result.confidence_label == "alta"
        assert result.is_reliable
