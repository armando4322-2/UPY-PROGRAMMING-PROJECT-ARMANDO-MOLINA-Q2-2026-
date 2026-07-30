#!/usr/bin/env python3
"""Recolector diario de metricas reales.

Este script es lo que convierte el proyecto en un agente de verdad. Hasta
ahora solo percibia cuando alguien lo ejecutaba a mano; ejecutado a diario
por GitHub Actions, percibe por su cuenta y acumula memoria.

El problema que resuelve
------------------------
Ninguna API publica devuelve los seguidores que un artista tenia hace
treinta dias. Se comprobo: Wayback Machine no conserva respuestas de la API
de Deezer, ListenBrainz solo agrega escuchas por usuario y Spotify bloquea
las metricas. El pasado, sencillamente, no esta disponible en ninguna parte.

La unica forma honesta de tener una serie temporal real es empezar a
medirla. Cada ejecucion anade un punto a `folk_analytics/data/history.json`,
que se versiona: el historial de commits del repositorio queda como prueba
de que los datos se recogieron ese dia y no se generaron despues.

Uso:
    python tools/collect_snapshots.py
    python tools/collect_snapshots.py --dry-run    # no escribe nada
"""

from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from folk_analytics.api.artists import load_catalog          # noqa: E402
from folk_analytics.api.base import StreamingAPIError        # noqa: E402
from folk_analytics.api.deezer import DeezerClient           # noqa: E402
from folk_analytics.logging_setup import setup_logging       # noqa: E402
from folk_analytics.storage.json_store import SnapshotStore  # noqa: E402

HISTORY_FILE = PROJECT_ROOT / "folk_analytics" / "data" / "history.json"

#: Pausa entre consultas. Deezer admite unas 50 peticiones cada 5 segundos;
#: con esto vamos muy por debajo y no se molesta a un servicio gratuito.
REQUEST_DELAY = 0.4


def collect(dry_run: bool = False) -> int:
    """Recoge una instantanea de cada artista del catalogo.

    Returns:
        Codigo de salida: 0 si al menos un artista se recogio correctamente.
    """
    setup_logging()

    catalog = load_catalog()
    if not catalog:
        print("ERROR: el catalogo esta vacio. Ejecuta tools/build_catalog.py")
        return 1

    store = SnapshotStore(path=HISTORY_FILE)
    client = DeezerClient()

    before = store.total_snapshots()
    added = updated = failed = 0

    print(f"  Recolectando {len(catalog)} artistas")
    print(f"  Historico previo: {before} instantaneas\n")

    for index, artist in enumerate(catalog, start=1):
        try:
            data = client.fetch_artist(artist.name)
        except StreamingAPIError as exc:
            failed += 1
            print(f"  {index:>2}. {artist.name:<22} FALLO: {str(exc)[:44]}")
            continue

        is_new = store.add(data, save=False)
        added += is_new
        updated += not is_new
        mark = "nuevo" if is_new else "actualizado"
        print(f"  {index:>2}. {data.name:<22} {data.followers:>12,}  ({mark})")
        time.sleep(REQUEST_DELAY)

    if dry_run:
        print("\n  --dry-run: no se ha escrito nada")
        return 0

    store.save()

    print(f"\n  Instantaneas nuevas   : {added}")
    print(f"  Actualizadas (mismo dia): {updated}")
    print(f"  Fallidas              : {failed}")
    print(f"  Total en el historico : {store.total_snapshots()}")
    print(f"  Artistas con historico: {len(store.known_artists())}")

    # Cuantos dias distintos cubre el historico: es lo que determina si ya
    # se pueden calcular tendencias reales.
    days = set()
    for artist_id in store.known_artists():
        for snapshot in store.history(artist_id):
            days.add(snapshot.captured_at.date().isoformat())
    print(f"  Dias cubiertos        : {len(days)}")

    if len(days) < 4:
        print(f"\n  Faltan {4 - len(days)} dias de recoleccion para que las "
              f"tendencias sean calculables.")

    return 0 if failed < len(catalog) else 1


if __name__ == "__main__":
    sys.exit(collect(dry_run="--dry-run" in sys.argv))
