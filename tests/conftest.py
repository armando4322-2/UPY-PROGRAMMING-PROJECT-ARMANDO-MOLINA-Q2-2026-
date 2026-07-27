"""Fixtures compartidas por la suite de tests."""

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from folk_analytics.api.models import ArtistData
from folk_analytics.api.simulated import SimulatedClient
from folk_analytics.storage.json_store import SnapshotStore, WatchlistStore


@pytest.fixture
def store(tmp_path):
    """Almacen de snapshots aislado en un directorio temporal."""
    return SnapshotStore(path=tmp_path / "snapshots.json")


@pytest.fixture
def watchlist(tmp_path):
    """Watchlist aislada en un directorio temporal."""
    return WatchlistStore(path=tmp_path / "watchlist.json")


@pytest.fixture
def client():
    """Cliente simulado sin fallos ni esperas, para tests deterministas."""
    return SimulatedClient(failure_rate=0.0, sleep_between_retries=False)


def make_snapshot(followers: int, days_ago: int = 0, artist_id: str = "ART-TEST") -> ArtistData:
    """Construye un snapshot sintetico para los tests."""
    return ArtistData(
        artist_id=artist_id,
        name="Artista de Prueba",
        followers=followers,
        monthly_listeners=followers // 2,
        popularity=50,
        source="test",
        captured_at=datetime.now(timezone.utc).replace(microsecond=0)
        - timedelta(days=days_ago),
    )
