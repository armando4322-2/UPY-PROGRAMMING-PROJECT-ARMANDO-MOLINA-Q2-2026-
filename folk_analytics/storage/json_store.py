"""Almacen de instantaneas en JSON.

Este modulo es la pieza que convierte el proyecto en un agente de verdad.
Sin historico persistente no hay tendencia posible: solo ruido. Aqui cada
consulta deja un rastro en disco que las ejecuciones futuras pueden leer.

Formato del archivo `data/snapshots.json`:

    {
      "ART-001": [ {snapshot}, {snapshot}, ... ],
      "ART-004": [ ... ]
    }

Las listas se mantienen ordenadas por fecha de captura y sin duplicados
del mismo dia.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from folk_analytics import config
from folk_analytics.api.models import ArtistData
from folk_analytics.logging_setup import get_logger

logger = get_logger("storage")


class SnapshotStore:
    """Guarda y consulta el historico de metricas por artista."""

    def __init__(self, path: Path | None = None):
        self.path = Path(path) if path else config.SNAPSHOT_FILE
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._data: dict[str, list[dict]] = self._load()

    # -- Entrada / salida -----------------------------------------------------

    def _load(self) -> dict[str, list[dict]]:
        """Lee el archivo de snapshots, tolerando ausencia o corrupcion."""
        if not self.path.exists():
            logger.debug("No existe historico previo en %s", self.path)
            return {}
        try:
            with self.path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
            total = sum(len(v) for v in data.values())
            logger.info(
                "Historico cargado: %d artistas, %d instantaneas", len(data), total
            )
            return data
        except (json.JSONDecodeError, OSError) as exc:
            logger.error("El historico esta corrupto o no se puede leer: %s", exc)
            backup = self.path.with_suffix(".corrupt.json")
            try:
                self.path.replace(backup)
                logger.warning("Archivo dañado movido a %s", backup.name)
            except OSError:
                pass
            return {}

    def save(self) -> None:
        """Vuelca el historico completo a disco."""
        tmp = self.path.with_suffix(".tmp")
        with tmp.open("w", encoding="utf-8") as handle:
            json.dump(self._data, handle, indent=2, ensure_ascii=False)
        tmp.replace(self.path)
        logger.debug("Historico guardado en %s", self.path)

    # -- Escritura ------------------------------------------------------------

    def add(self, data: ArtistData, save: bool = True) -> bool:
        """Registra una instantanea.

        Si ya existe una del mismo dia para ese artista, la reemplaza en
        lugar de duplicarla.

        Returns:
            True si se anadio una entrada nueva, False si se reemplazo.
        """
        entries = self._data.setdefault(data.artist_id, [])
        day = data.captured_at.date().isoformat()

        is_new = True
        for index, existing in enumerate(entries):
            if existing["captured_at"][:10] == day:
                entries[index] = data.to_dict()
                is_new = False
                break
        else:
            entries.append(data.to_dict())

        entries.sort(key=lambda item: item["captured_at"])

        if save:
            self.save()

        logger.debug(
            "Instantanea %s para %s (%s)",
            "anadida" if is_new else "actualizada",
            data.name,
            day,
        )
        return is_new

    # -- Lectura --------------------------------------------------------------

    def history(self, artist_id: str, days: int | None = None) -> list[ArtistData]:
        """Devuelve el historico de un artista, opcionalmente acotado.

        Args:
            artist_id: identificador del artista.
            days: si se indica, solo instantaneas de los ultimos N dias.
        """
        entries = self._data.get(artist_id, [])
        records = [ArtistData.from_dict(entry) for entry in entries]

        if days is not None:
            cutoff = datetime.now(timezone.utc) - timedelta(days=days)
            records = [r for r in records if r.captured_at >= cutoff]

        return records

    def has_history(self, artist_id: str, minimum: int = 1) -> bool:
        """True si hay al menos `minimum` instantaneas registradas."""
        return len(self._data.get(artist_id, [])) >= minimum

    def known_artists(self) -> list[str]:
        """Identificadores de todos los artistas con historico."""
        return sorted(self._data.keys())

    def latest(self, artist_id: str) -> ArtistData | None:
        """Ultima instantanea registrada de un artista, o None."""
        entries = self._data.get(artist_id, [])
        return ArtistData.from_dict(entries[-1]) if entries else None

    def total_snapshots(self) -> int:
        """Numero total de instantaneas almacenadas."""
        return sum(len(entries) for entries in self._data.values())

    def clear(self, save: bool = True) -> None:
        """Borra todo el historico. Util en tests y para reiniciar el agente."""
        self._data = {}
        if save:
            self.save()
        logger.warning("Historico borrado por completo")


class WatchlistStore:
    """Lista de artistas bajo vigilancia del agente."""

    def __init__(self, path: Path | None = None):
        self.path = Path(path) if path else config.WATCHLIST_FILE
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._names: list[str] = self._load()

    def _load(self) -> list[str]:
        if not self.path.exists():
            return []
        try:
            with self.path.open("r", encoding="utf-8") as handle:
                names = json.load(handle)
            return [str(n) for n in names]
        except (json.JSONDecodeError, OSError) as exc:
            logger.error("No se pudo leer la watchlist: %s", exc)
            return []

    def save(self) -> None:
        with self.path.open("w", encoding="utf-8") as handle:
            json.dump(self._names, handle, indent=2, ensure_ascii=False)

    def add(self, artist_name: str) -> bool:
        """Anade un artista. Devuelve False si ya estaba."""
        name = artist_name.strip()
        if any(n.lower() == name.lower() for n in self._names):
            return False
        self._names.append(name)
        self.save()
        logger.info("'%s' anadido a la watchlist", name)
        return True

    def remove(self, artist_name: str) -> bool:
        """Quita un artista. Devuelve False si no estaba."""
        name = artist_name.strip().lower()
        for existing in self._names:
            if existing.lower() == name:
                self._names.remove(existing)
                self.save()
                logger.info("'%s' eliminado de la watchlist", existing)
                return True
        return False

    def all(self) -> list[str]:
        """Copia de la lista de artistas vigilados."""
        return list(self._names)

    def __len__(self) -> int:
        return len(self._names)
