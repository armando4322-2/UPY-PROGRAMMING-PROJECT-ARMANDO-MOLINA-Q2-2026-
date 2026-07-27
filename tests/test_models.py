"""Tests del modelo de datos."""

from folk_analytics.api.models import ArtistData
from tests.conftest import make_snapshot


class TestArtistData:
    def test_serializa_y_deserializa(self):
        original = make_snapshot(1234)
        recuperado = ArtistData.from_dict(original.to_dict())
        assert recuperado == original

    def test_to_dict_produce_fecha_en_texto(self):
        assert isinstance(make_snapshot(1).to_dict()["captured_at"], str)

    def test_has_activity_con_seguidores(self):
        assert make_snapshot(100).has_activity

    def test_has_activity_sin_nada(self):
        assert not make_snapshot(0).has_activity

    def test_es_inmutable(self):
        snapshot = make_snapshot(100)
        try:
            snapshot.followers = 999
        except Exception:
            return
        raise AssertionError("ArtistData deberia ser inmutable")
