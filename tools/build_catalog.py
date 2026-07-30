#!/usr/bin/env python3
"""Genera el catalogo de artistas destacados.

Combina tres fuentes, cada una en lo que hace bien:

    Deezer      identificador y metricas reales (verificadas)
    Spotify     foto oficial en alta resolucion
    MusicBrainz pais, tipo y generos, para la descripcion

Se ejecuta sin conexion con el proyecto, no en tiempo de uso: el resultado
se guarda en `folk_analytics/data/catalog.json` y se versiona. Asi la
pagina web no necesita credenciales de Spotify para mostrar las fotos.

Que se guarda y que no
----------------------
Solo entra en el catalogo lo que apenas cambia: identificadores, foto, pais,
generos. Los seguidores NO se guardan: quedarian congelados en la fecha de
generacion y el proyecto acabaria mostrando cifras caducadas como si fueran
actuales. Se consultan en vivo en cada analisis.

Uso:
    python tools/build_catalog.py
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from folk_analytics.api.base import ArtistNotFoundError      # noqa: E402
from folk_analytics.api.matching import select_best_match    # noqa: E402

OUTPUT = PROJECT_ROOT / "folk_analytics" / "data" / "catalog.json"
USER_AGENT = "FolkAnalytics/2.3 (proyecto academico UPY)"

# MusicBrainz pide como maximo una peticion por segundo.
MUSICBRAINZ_DELAY = 1.1

ARTISTS = [
    "Mon Laferte", "Michael Jackson", "Tito Double P", "Peso Pluma",
    "Rauw Alejandro", "Joji", "Bad Bunny", "Junior H", "Zell",
    "Fuerza Regida", "El De Las R's", "Queen", "Young Cister",
    "Black Eyed Peas", "Ivan Cornejo", "Calle 24", "The Weeknd", "Rojuu",
    "kensuke ushio", "Bruno Mars", "Natanael Cano", "Luis Miguel", "Drake",
    "Josean Log", "Chuyin", "NewJeans",
]


def get_json(url, headers=None):
    request = urllib.request.Request(
        url, headers={"User-Agent": USER_AGENT, **(headers or {})}
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def spotify_token():
    """Token de aplicacion, o None si no hay credenciales configuradas."""
    env = PROJECT_ROOT / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.strip().startswith("#"):
                key, _, value = line.partition("=")
                os.environ.setdefault(key.strip(), value.strip())

    client_id = os.environ.get("SPOTIFY_CLIENT_ID")
    secret = os.environ.get("SPOTIFY_CLIENT_SECRET")
    if not client_id or not secret:
        print("  ! Sin credenciales de Spotify: se usaran las fotos de Deezer")
        return None

    body = urllib.parse.urlencode({
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": secret,
    }).encode()
    request = urllib.request.Request(
        "https://accounts.spotify.com/api/token", data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode())["access_token"]


def from_deezer(name):
    payload = get_json(
        "https://api.deezer.com/search/artist?"
        + urllib.parse.urlencode({"q": name, "limit": 10})
    )
    best = select_best_match(
        payload.get("data") or [], name,
        name_of=lambda c: c.get("name", ""),
        rank_of=lambda c: c.get("nb_fan", 0),
        source="Deezer",
    )
    return {
        "name": best["name"],
        "deezer_id": best["id"],
        "deezer_image": best.get("picture_xl") or best.get("picture_big"),
        "fans": best.get("nb_fan", 0),
    }


def from_spotify(name, token):
    """Foto oficial. Spotify ya no expone metricas a las apps nuevas.

    Verificado el 2026-07-30: /v1/artists/{id} responde 200 pero sin
    followers, popularity ni genres, y /v1/artists?ids= devuelve 403.
    Por eso Spotify solo aporta identidad e imagen.
    """
    payload = get_json(
        "https://api.spotify.com/v1/search?"
        + urllib.parse.urlencode({"q": name, "type": "artist", "limit": 10}),
        {"Authorization": "Bearer " + token},
    )
    items = (payload.get("artists") or {}).get("items") or []
    best = select_best_match(
        items, name,
        name_of=lambda c: c.get("name", ""),
        rank_of=lambda c: 0,
        source="Spotify",
    )
    images = best.get("images") or []
    return {
        "spotify_id": best["id"],
        "spotify_image": images[0]["url"] if images else None,
    }


def from_musicbrainz(name):
    """Pais, tipo y generos, que es lo que alimenta la descripcion."""
    payload = get_json(
        "https://musicbrainz.org/ws/2/artist?"
        + urllib.parse.urlencode({"query": 'artist:"%s"' % name, "fmt": "json", "limit": 1})
    )
    artists = payload.get("artists") or []
    if not artists:
        return {}

    artist = artists[0]
    tags = sorted(artist.get("tags") or [], key=lambda t: -t.get("count", 0))
    return {
        "country": artist.get("country"),
        "kind": artist.get("type"),
        "gender": artist.get("gender"),
        "genres": [t["name"] for t in tags[:3]],
        "began": (artist.get("life-span") or {}).get("begin"),
    }


def load_existing():
    """Entradas ya resueltas, para poder reanudar.

    MusicBrainz limita a una peticion por segundo, asi que generar el
    catalogo entero lleva alrededor de un minuto. Reanudar evita rehacer el
    trabajo si el proceso se interrumpe a mitad.
    """
    if not OUTPUT.exists():
        return {}
    try:
        data = json.loads(OUTPUT.read_text(encoding="utf-8"))
        return {e["name"]: e for e in data.get("artists", [])}
    except (json.JSONDecodeError, OSError, KeyError):
        return {}


def save(entries):
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps({
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "note": ("Generado por tools/build_catalog.py. Solo contiene datos estables. "
                 "Las metricas se consultan en vivo para no mostrar cifras caducadas."),
        "artists": entries,
    }, ensure_ascii=False, indent=2), encoding="utf-8")


def build(force=False, budget=None):
    """Genera el catalogo.

    Args:
        force : rehace las entradas ya existentes.
        budget: segundos maximos de trabajo antes de guardar y salir. Permite
            trabajar por tandas cuando hay limite de tiempo por ejecucion.
    """
    started = time.time()
    token = spotify_token()
    existing = {} if force else load_existing()
    entries = []
    failures = []
    resolved = skipped = 0

    print("  Resolviendo %d artistas (%d ya en catalogo)...\n"
          % (len(ARTISTS), len(existing)))

    for index, name in enumerate(ARTISTS, start=1):
        previous = next(
            (e for key, e in existing.items()
             if key.casefold() == name.casefold() or e.get("query", "").casefold() == name.casefold()),
            None,
        )
        if previous is not None:
            entries.append(previous)
            skipped += 1
            continue

        if budget is not None and time.time() - started > budget:
            entries.extend(
                e for e in existing.values()
                if e["name"] not in {x["name"] for x in entries}
            )
            save(entries)
            print("\n  Tanda completada: %d nuevos, %d pendientes. Vuelve a ejecutar."
                  % (resolved, len(ARTISTS) - len(entries)))
            return OUTPUT

        entry = {"name": name, "query": name}
        marks = []

        try:
            deezer = from_deezer(name)
            entry["name"] = deezer["name"]
            entry["deezer_id"] = deezer["deezer_id"]
            entry["image"] = deezer["deezer_image"]
            marks.append("deezer %10s" % format(deezer["fans"], ","))
        except (ArtistNotFoundError, urllib.error.URLError, KeyError) as exc:
            failures.append("%s: Deezer -> %s" % (name, exc))
            marks.append("deezer ---")

        if token:
            try:
                spotify = from_spotify(name, token)
                entry["spotify_id"] = spotify["spotify_id"]
                if spotify["spotify_image"]:
                    entry["image"] = spotify["spotify_image"]   # mejor resolucion
                marks.append("foto spotify")
            except (ArtistNotFoundError, urllib.error.URLError, KeyError) as exc:
                failures.append("%s: Spotify -> %s" % (name, exc))
                marks.append("foto deezer")

        try:
            extra = from_musicbrainz(name)
            entry.update({k: v for k, v in extra.items() if v})
            marks.append(",".join(entry.get("genres", [])[:2]) or "sin generos")
        except (urllib.error.URLError, KeyError) as exc:
            failures.append("%s: MusicBrainz -> %s" % (name, exc))
        time.sleep(MUSICBRAINZ_DELAY)

        entries.append(entry)
        resolved += 1
        save(entries)
        print("  %2d. %-20s %s" % (index, entry["name"][:20], " | ".join(marks)))

    save(entries)
    print("\n  Artistas en el catalogo : %d (%d nuevos, %d reutilizados)"
          % (len(entries), resolved, skipped))
    print("  Con foto                : %d" % sum(1 for e in entries if e.get("image")))
    print("  Con generos             : %d" % sum(1 for e in entries if e.get("genres")))
    if failures:
        print("\n  Incidencias (%d):" % len(failures))
        for failure in failures:
            print("    - %s" % failure)
    print("\n  Escrito en %s" % OUTPUT.relative_to(PROJECT_ROOT))
    return OUTPUT


if __name__ == "__main__":
    build(
        force="--force" in sys.argv,
        budget=float(sys.argv[sys.argv.index("--budget") + 1])
        if "--budget" in sys.argv else None,
    )
