"""Tests de persistencia."""

from folk_analytics.storage.json_store import SnapshotStore
from tests.conftest import make_snapshot


class TestSnapshotStore:
    def test_arranca_vacio(self, store):
        assert store.total_snapshots() == 0
        assert store.known_artists() == []

    def test_guarda_y_recupera(self, store):
        store.add(make_snapshot(1000))
        history = store.history("ART-TEST")
        assert len(history) == 1
        assert history[0].followers == 1000

    def test_no_duplica_el_mismo_dia(self, store):
        assert store.add(make_snapshot(1000)) is True
        assert store.add(make_snapshot(1200)) is False
        history = store.history("ART-TEST")
        assert len(history) == 1
        assert history[0].followers == 1200  # se queda el ultimo valor

    def test_acumula_dias_distintos(self, store):
        for days_ago in range(5):
            store.add(make_snapshot(1000 + days_ago, days_ago=days_ago))
        assert len(store.history("ART-TEST")) == 5

    def test_ordena_cronologicamente(self, store):
        store.add(make_snapshot(300, days_ago=1))
        store.add(make_snapshot(100, days_ago=3))
        store.add(make_snapshot(200, days_ago=2))
        followers = [s.followers for s in store.history("ART-TEST")]
        assert followers == [100, 200, 300]

    def test_filtra_por_ventana_de_dias(self, store):
        store.add(make_snapshot(100, days_ago=50))
        store.add(make_snapshot(200, days_ago=2))
        assert len(store.history("ART-TEST")) == 2
        assert len(store.history("ART-TEST", days=30)) == 1

    def test_has_history_respeta_el_minimo(self, store):
        store.add(make_snapshot(100, days_ago=1))
        store.add(make_snapshot(200, days_ago=2))
        assert store.has_history("ART-TEST", minimum=2)
        assert not store.has_history("ART-TEST", minimum=3)

    def test_latest_devuelve_el_mas_reciente(self, store):
        store.add(make_snapshot(100, days_ago=5))
        store.add(make_snapshot(999, days_ago=0))
        assert store.latest("ART-TEST").followers == 999

    def test_latest_sin_datos_devuelve_none(self, store):
        assert store.latest("NO-EXISTE") is None

    def test_persiste_entre_instancias(self, store, tmp_path):
        store.add(make_snapshot(4242))
        recargado = SnapshotStore(path=tmp_path / "snapshots.json")
        assert recargado.history("ART-TEST")[0].followers == 4242

    def test_clear_borra_todo(self, store):
        store.add(make_snapshot(100))
        store.clear()
        assert store.total_snapshots() == 0

    def test_archivo_corrupto_no_revienta(self, tmp_path):
        path = tmp_path / "snapshots.json"
        path.write_text("{esto no es json valido", encoding="utf-8")
        recuperado = SnapshotStore(path=path)
        assert recuperado.total_snapshots() == 0

    def test_separa_artistas_distintos(self, store):
        store.add(make_snapshot(100, artist_id="ART-A"))
        store.add(make_snapshot(200, artist_id="ART-B"))
        assert store.known_artists() == ["ART-A", "ART-B"]
        assert store.history("ART-A")[0].followers == 100


class TestWatchlistStore:
    def test_arranca_vacia(self, watchlist):
        assert len(watchlist) == 0

    def test_anade_artista(self, watchlist):
        assert watchlist.add("AURORA") is True
        assert watchlist.all() == ["AURORA"]

    def test_no_duplica_ignorando_mayusculas(self, watchlist):
        watchlist.add("AURORA")
        assert watchlist.add("aurora") is False
        assert len(watchlist) == 1

    def test_quita_artista(self, watchlist):
        watchlist.add("AURORA")
        assert watchlist.remove("aurora") is True
        assert len(watchlist) == 0

    def test_quitar_inexistente_devuelve_false(self, watchlist):
        assert watchlist.remove("Nadie") is False
