"""Tests del cliente de datos simulados."""

from datetime import datetime, timedelta, timezone

import pytest

from folk_analytics.api.base import ArtistNotFoundError, StreamingAPIError
from folk_analytics.api.simulated import SimulatedClient


class TestSimulatedClient:
    def test_recupera_un_artista_conocido(self, client):
        data = client.fetch_artist("AURORA")
        assert data.artist_id == "ART-001"
        assert data.followers > 0

    def test_es_insensible_a_mayusculas(self, client):
        assert client.fetch_artist("aurora").artist_id == "ART-001"

    def test_ignora_espacios_alrededor(self, client):
        assert client.fetch_artist("  AURORA  ").artist_id == "ART-001"

    def test_artista_inexistente_lanza_error(self, client):
        with pytest.raises(ArtistNotFoundError):
            client.fetch_artist("Artista Que No Existe")

    def test_el_catalogo_no_esta_vacio(self, client):
        assert len(client.available_artists()) > 0

    def test_es_determinista_en_la_misma_fecha(self, client):
        """El bug central de la version anterior: los datos cambiaban en
        cada ejecucion, asi que la 'tendencia' medía ruido."""
        dia = datetime.now(timezone.utc).date() - timedelta(days=5)
        primera = client.fetch_artist_at("AURORA", dia)
        segunda = client.fetch_artist_at("AURORA", dia)
        assert primera.followers == segunda.followers
        assert primera.monthly_listeners == segunda.monthly_listeners

    def test_fechas_distintas_dan_valores_distintos(self, client):
        hoy = datetime.now(timezone.utc).date()
        a = client.fetch_artist_at("AURORA", hoy - timedelta(days=1))
        b = client.fetch_artist_at("AURORA", hoy - timedelta(days=20))
        assert a.followers != b.followers

    def test_un_artista_en_crecimiento_crece_con_el_tiempo(self, client):
        """Novo Amor tiene tasa positiva: el pasado debe ser menor."""
        hoy = datetime.now(timezone.utc).date()
        pasado = client.fetch_artist_at("Novo Amor", hoy - timedelta(days=60))
        actual = client.fetch_artist_at("Novo Amor", hoy)
        assert pasado.followers < actual.followers

    def test_un_artista_en_declive_decrece(self, client):
        hoy = datetime.now(timezone.utc).date()
        pasado = client.fetch_artist_at("Hollow Pines", hoy - timedelta(days=60))
        actual = client.fetch_artist_at("Hollow Pines", hoy)
        assert pasado.followers > actual.followers

    def test_la_popularidad_se_mantiene_en_rango(self, client):
        """Es un indice 0-100, no un contador: no puede desbordarse."""
        hoy = datetime.now(timezone.utc).date()
        for dias in range(0, 200, 7):
            data = client.fetch_artist_at("Hollow Pines", hoy - timedelta(days=dias))
            assert 0 <= data.popularity <= 100

    def test_la_popularidad_evoluciona_con_el_tiempo(self, client):
        """Si fuera constante, la metrica 'popularity' no diria nada."""
        hoy = datetime.now(timezone.utc).date()
        valores = {
            client.fetch_artist_at("Hollow Pines", hoy - timedelta(days=d)).popularity
            for d in range(0, 30, 5)
        }
        assert len(valores) > 1

    def test_la_popularidad_tambien_es_determinista(self, client):
        dia = datetime.now(timezone.utc).date() - timedelta(days=9)
        a = client.fetch_artist_at("AURORA", dia).popularity
        b = client.fetch_artist_at("AURORA", dia).popularity
        assert a == b

    def test_artista_sin_actividad(self, client):
        data = client.fetch_artist("unknown artist")
        assert not data.has_activity

    def test_reintenta_y_acaba_fallando(self):
        """Con fallo garantizado debe agotar reintentos y lanzar error.

        En la version anterior el codigo registraba 'reintentando...'
        pero no reintentaba nada.
        """
        roto = SimulatedClient(failure_rate=1.0, sleep_between_retries=False)
        with pytest.raises(StreamingAPIError):
            roto.fetch_artist("AURORA")

    def test_sin_fallos_no_lanza_nunca(self, client):
        for _ in range(30):
            assert client.fetch_artist("AURORA") is not None
