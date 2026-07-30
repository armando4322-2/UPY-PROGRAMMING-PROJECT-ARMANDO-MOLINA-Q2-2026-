"""Tests del top de canciones.

Los payloads reproducen la forma real de la respuesta de Deezer, capturada
de la API el 2026-07-30.
"""

import pytest

from folk_analytics.api.base import StreamingAPIError
from folk_analytics.api.deezer import PrefetchedDeezerClient, parse_top_tracks
from folk_analytics.api.models import Track


def track(title, album="Un Album", rank=500_000, duration=210):
    return {
        "id": 1, "title": title, "title_short": title,
        "duration": duration, "rank": rank,
        "preview": "https://cdn-preview.deezer.com/x.mp3",
        "link": "https://www.deezer.com/track/1",
        "album": {"id": 9, "title": album},
        "artist": {"id": 7, "name": "Artista"},
    }


class TestTrackModel:
    def test_formatea_la_duracion(self):
        assert Track(1, "T", "A", 0, 237).duration == "3:57"

    def test_duracion_con_segundos_de_una_cifra(self):
        assert Track(1, "T", "A", 0, 185).duration == "3:05"

    def test_duracion_cero(self):
        assert Track(1, "T", "A", 0, 0).duration == "0:00"

    def test_duracion_negativa_no_rompe(self):
        assert Track(1, "T", "A", 0, -5).duration == "0:00"

    def test_duracion_larga(self):
        assert Track(1, "T", "A", 0, 472).duration == "7:52"

    def test_serializa_incluyendo_la_duracion_legible(self):
        assert Track(1, "T", "A", 0, 237).to_dict()["duration"] == "3:57"


class TestParseTopTracks:
    def test_numera_las_posiciones_desde_uno(self):
        tracks = parse_top_tracks({"data": [track("A"), track("B"), track("C")]})
        assert [t.position for t in tracks] == [1, 2, 3]

    def test_extrae_titulo_y_album(self):
        tracks = parse_top_tracks({"data": [track("Viento", "Caifanes")]})
        assert tracks[0].title == "Viento"
        assert tracks[0].album == "Caifanes"

    def test_respeta_el_limite(self):
        tracks = parse_top_tracks({"data": [track(f"T{i}") for i in range(25)]}, limit=10)
        assert len(tracks) == 10

    def test_sin_canciones_devuelve_vacio(self):
        assert parse_top_tracks({"data": []}) == ()

    def test_titulo_ausente_no_rompe(self):
        tracks = parse_top_tracks({"data": [{"title": "", "album": {}}]})
        assert tracks[0].title == "Sin titulo"

    def test_album_ausente_queda_vacio(self):
        tracks = parse_top_tracks({"data": [{"title": "X"}]})
        assert tracks[0].album == ""

    def test_valores_nulos_se_tratan_como_cero(self):
        tracks = parse_top_tracks({"data": [{"title": "X", "rank": None, "duration": None}]})
        assert tracks[0].rank == 0 and tracks[0].duration_seconds == 0

    def test_error_de_la_api_se_propaga(self):
        with pytest.raises(StreamingAPIError, match="Quota"):
            parse_top_tracks({"error": {"message": "Quota limit exceeded"}})

    def test_formato_inesperado(self):
        with pytest.raises(StreamingAPIError):
            parse_top_tracks("no es un diccionario")


class TestClienteConTopPrecargado:
    """El cliente de la web recibe el top ya descargado por JavaScript y debe
    interpretarlo con la misma logica que la version de consola."""

    def test_devuelve_el_top(self, ):
        from folk_analytics.api.models import ArtistData, utcnow

        client = PrefetchedDeezerClient(
            {"data": [{"id": 1, "name": "Caifanes", "nb_fan": 855_561, "nb_album": 30}]},
            top_payload={"data": [track("Viento"), track("Afuera")]},
        )
        artist = ArtistData("DZ-1", "Caifanes", 855_561, 0, 0, "deezer", utcnow())
        tracks = client.fetch_top_tracks(artist)
        assert [t.title for t in tracks] == ["Viento", "Afuera"]

    def test_sin_top_precargado_devuelve_vacio(self):
        from folk_analytics.api.models import ArtistData, utcnow

        client = PrefetchedDeezerClient({"data": []})
        artist = ArtistData("DZ-1", "X", 1, 0, 0, "deezer", utcnow())
        assert client.fetch_top_tracks(artist) == ()


class TestRenderizado:
    def test_el_reporte_incluye_la_seccion(self):
        from folk_analytics.analytics.metrics import summarize
        from folk_analytics.analytics.trends import analyze_trend
        from folk_analytics.api.models import ArtistData, utcnow
        from folk_analytics.reports.console import render_report

        snapshot = ArtistData("DZ-1", "Caifanes", 855_561, 0, 0, "deezer", utcnow())
        report = render_report(
            "TEST", snapshot, summarize([snapshot]), analyze_trend([1.0]), [], [],
            tracks=(Track(1, "Viento", "Caifanes", 617_951, 237),),
        )
        assert "TOP 1 CANCIONES" in report
        assert "Viento" in report
        assert "3:57" in report

    def test_sin_canciones_no_aparece_la_seccion(self):
        from folk_analytics.analytics.metrics import summarize
        from folk_analytics.analytics.trends import analyze_trend
        from folk_analytics.api.models import ArtistData, utcnow
        from folk_analytics.reports.console import render_report

        snapshot = ArtistData("S-1", "X", 100, 0, 0, "simulated", utcnow())
        report = render_report("T", snapshot, summarize([snapshot]), analyze_trend([1.0]), [], [])
        assert "CANCIONES" not in report
