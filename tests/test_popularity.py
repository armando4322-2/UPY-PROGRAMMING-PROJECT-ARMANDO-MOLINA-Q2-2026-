"""Tests del indice de popularidad derivado."""

from folk_analytics.analytics.popularity import (
    INDEX_MAX,
    SOURCE_RANK_MAX,
    mean_track_rank,
    popularity_index,
)
from folk_analytics.api.models import Track


def tracks(*ranks):
    return tuple(
        Track(position=i, title=f"T{i}", album="A", rank=r, duration_seconds=200)
        for i, r in enumerate(ranks, start=1)
    )


class TestMeanTrackRank:
    def test_media_simple(self):
        assert mean_track_rank(tracks(100, 200, 300)) == 200

    def test_ignora_canciones_sin_rango(self):
        """Un rango 0 significa que la fuente no lo publica para esa cancion;
        incluirlo hundiria la media con un dato que no existe."""
        assert mean_track_rank(tracks(400, 0, 600)) == 500

    def test_sin_canciones(self):
        assert mean_track_rank(()) == 0.0

    def test_todas_sin_rango(self):
        assert mean_track_rank(tracks(0, 0)) == 0.0


class TestPopularityIndex:
    def test_convierte_el_rango_de_deezer_a_escala_0_100(self):
        assert popularity_index(tracks(SOURCE_RANK_MAX)) == INDEX_MAX

    def test_media_de_medio_millon_da_cincuenta(self):
        assert popularity_index(tracks(500_000, 500_000)) == 50

    def test_caso_real_caifanes(self):
        """Rangos reales capturados de la API: media 564.488 -> 56."""
        reales = tracks(617_951, 616_460, 622_421, 600_363, 587_268,
                        543_630, 523_927, 549_740, 475_791, 507_331)
        assert popularity_index(reales) == 56

    def test_caso_real_taylor_swift(self):
        """Mas popular que Caifanes, y el indice debe reflejarlo."""
        reales = tracks(999_852, 970_000, 900_000, 870_000, 850_000,
                        830_000, 800_000, 790_000, 770_000, 753_312)
        indice = popularity_index(reales)
        assert indice == 85
        assert indice > popularity_index(tracks(564_488))

    def test_sin_canciones_devuelve_cero(self):
        assert popularity_index(()) == 0

    def test_artista_sin_actividad(self):
        assert popularity_index(tracks(0, 0, 0)) == 0

    def test_nunca_supera_cien(self):
        assert popularity_index(tracks(SOURCE_RANK_MAX * 3)) == INDEX_MAX

    def test_nunca_es_negativo(self):
        assert popularity_index(tracks(-500)) == 0

    def test_usa_la_media_y_no_el_maximo(self):
        """Un exito viral aislado no debe describir a todo el repertorio."""
        un_hit = tracks(1_000_000, 10_000, 10_000, 10_000, 10_000)
        assert popularity_index(un_hit) < 30

    def test_es_comparable_entre_artistas(self):
        grande = popularity_index(tracks(900_000, 880_000, 870_000))
        pequeno = popularity_index(tracks(90_000, 88_000, 87_000))
        assert grande > pequeno * 5
