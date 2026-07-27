"""Tests de integracion del agente completo."""

import pytest

from folk_analytics.agent import FolkAnalyticsAgent, InvalidInputError
from folk_analytics.analytics.trends import TrendDirection
from folk_analytics.api.base import ArtistNotFoundError


@pytest.fixture
def agent(client, store):
    return FolkAnalyticsAgent(client=client, store=store)


class TestFolkAnalyticsAgent:
    def test_analiza_un_artista_de_punta_a_punta(self, agent):
        result = agent.analyze("AURORA")
        assert result.snapshot.name == "AURORA"
        assert result.session_id
        assert result.summary.sample_size > 0

    def test_reconstruye_historico_en_la_primera_consulta(self, agent, store):
        assert store.total_snapshots() == 0
        agent.analyze("AURORA")
        assert store.total_snapshots() >= 30

    def test_la_segunda_consulta_no_duplica_el_historico(self, agent, store):
        agent.analyze("AURORA")
        primer_total = store.total_snapshots()
        agent.analyze("AURORA")
        assert store.total_snapshots() == primer_total

    def test_con_historico_la_tendencia_es_calculable(self, agent):
        result = agent.analyze("AURORA")
        assert result.trend.direction is not TrendDirection.INSUFFICIENT_DATA

    def test_detecta_el_declive_de_un_artista_en_caida(self, agent):
        result = agent.analyze("Hollow Pines")
        assert result.trend.direction is TrendDirection.DECLINING
        assert result.trend.change_pct < 0

    def test_detecta_el_crecimiento_de_un_artista_al_alza(self, agent):
        result = agent.analyze("Novo Amor")
        assert result.trend.change_pct > 0

    def test_entrada_vacia_lanza_error_de_validacion(self, agent):
        with pytest.raises(InvalidInputError):
            agent.analyze("")

    def test_artista_inexistente_lanza_su_error(self, agent):
        with pytest.raises(ArtistNotFoundError):
            agent.analyze("Artista Inventado 12345")

    def test_el_reporte_se_renderiza_sin_fallar(self, agent):
        reporte = agent.analyze("AURORA").to_report()
        assert "FOLK ANALYTICS" in reporte
        assert "AURORA" in reporte
        assert "TENDENCIA" in reporte

    def test_metrica_alternativa(self, client, store):
        agente = FolkAnalyticsAgent(client=client, store=store, metric="monthly_listeners")
        assert agente.analyze("AURORA").metric == "monthly_listeners"


class TestAnalyzeMany:
    def test_separa_exitos_de_errores(self, agent):
        results, errors = agent.analyze_many(
            ["AURORA", "", "Novo Amor", "Artista Inventado 999"]
        )
        assert len(results) == 2
        assert len(errors) == 2

    def test_un_fallo_no_detiene_el_lote(self, agent):
        results, _ = agent.analyze_many(["No Existe", "AURORA"])
        assert len(results) == 1
        assert results[0].snapshot.name == "AURORA"

    def test_lote_vacio(self, agent):
        assert agent.analyze_many([]) == ([], [])
