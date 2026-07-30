"""Interfaz de linea de comandos con menu numerico.

Toda entrada del usuario pasa por validacion; el programa nunca debe
terminar por una excepcion no controlada a causa de lo que se teclee.
"""

from __future__ import annotations

from folk_analytics import __version__, config
from folk_analytics.agent import FolkAnalyticsAgent, InvalidInputError
from folk_analytics.api.base import ArtistNotFoundError, StreamingAPIError
from folk_analytics.logging_setup import get_logger
from folk_analytics.reports.console import render_summary_table
from folk_analytics.storage.json_store import WatchlistStore

logger = get_logger("cli")

MENU = """
==============================================================
  FOLK ANALYTICS v{version}  |  fuente: {source}
==============================================================
  1) Analizar un artista
  2) Ver catalogo de artistas disponibles
  3) Gestionar watchlist
  4) Analizar toda la watchlist
  5) Ver configuracion actual
  6) Borrar historico almacenado
  0) Salir
=============================================================="""

WATCHLIST_MENU = """
--------------------------------------------------------------
  WATCHLIST  ({count} artistas)
--------------------------------------------------------------
  1) Ver la lista
  2) Anadir un artista
  3) Quitar un artista
  0) Volver
--------------------------------------------------------------"""


def prompt_int(message: str, valid: set[int]) -> int:
    """Pide un numero al usuario hasta que introduzca uno valido."""
    while True:
        try:
            raw = input(message).strip()
        except (EOFError, KeyboardInterrupt):
            print("\n  Entrada interrumpida. Saliendo.")
            return 0

        if not raw:
            print("  ! Debes escribir una opcion.")
            continue

        try:
            value = int(raw)
        except ValueError:
            print(f"  ! '{raw}' no es un numero. Usa una de las opciones del menu.")
            continue

        if value not in valid:
            print(f"  ! La opcion {value} no existe. Elige entre {sorted(valid)}.")
            continue

        return value


def prompt_text(message: str) -> str:
    """Pide texto al usuario, devolviendo cadena vacia si se interrumpe."""
    try:
        return input(message).strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return ""


class FolkAnalyticsCLI:
    """Bucle interactivo del agente."""

    def __init__(self, agent: FolkAnalyticsAgent | None = None):
        self.agent = agent or FolkAnalyticsAgent()
        self.watchlist = WatchlistStore()

    # -- Acciones -------------------------------------------------------------

    def analyze_one(self) -> None:
        """Opcion 1: analizar un artista introducido por el usuario."""
        name = prompt_text("\n  Nombre del artista: ")
        self._run_analysis(name)

    def _run_analysis(self, name: str) -> None:
        """Ejecuta el analisis capturando todos los errores esperables."""
        try:
            result = self.agent.analyze(name)
        except InvalidInputError as exc:
            print(f"\n  ! Entrada no valida: {exc}\n")
        except ArtistNotFoundError:
            print(f"\n  ! No se encontro el artista '{name}'.")
            print("    Usa la opcion 2 para ver el catalogo disponible.\n")
        except StreamingAPIError as exc:
            print(f"\n  ! La fuente de datos fallo: {exc}\n")
        else:
            print(result.to_report())

    def show_catalog(self) -> None:
        """Opcion 2: listar los artistas conocidos por la fuente."""
        artists = self.agent.catalog()
        print("\n  CATALOGO DISPONIBLE")
        print("  " + "-" * 40)
        if not artists:
            print("  Esta fuente no permite enumerar su catalogo.")
            print("  Escribe el nombre del artista directamente.")
        else:
            for index, name in enumerate(artists, start=1):
                print(f"  {index:>2}. {name}")
        print()

    def manage_watchlist(self) -> None:
        """Opcion 3: submenu de gestion de la watchlist."""
        while True:
            print(WATCHLIST_MENU.format(count=len(self.watchlist)))
            choice = prompt_int("  Opcion: ", {0, 1, 2, 3})

            if choice == 0:
                return

            if choice == 1:
                names = self.watchlist.all()
                if not names:
                    print("\n  La watchlist esta vacia.\n")
                else:
                    print()
                    for index, name in enumerate(names, start=1):
                        print(f"  {index:>2}. {name}")
                    print()

            elif choice == 2:
                name = prompt_text("  Artista a anadir: ")
                if not name:
                    print("  ! Nombre vacio, no se anadio nada.\n")
                elif self.watchlist.add(name):
                    print(f"  '{name}' anadido a la watchlist.\n")
                else:
                    print(f"  '{name}' ya estaba en la watchlist.\n")

            elif choice == 3:
                name = prompt_text("  Artista a quitar: ")
                if self.watchlist.remove(name):
                    print(f"  '{name}' eliminado de la watchlist.\n")
                else:
                    print(f"  '{name}' no estaba en la watchlist.\n")

    def analyze_watchlist(self) -> None:
        """Opcion 4: analizar de golpe todos los artistas vigilados."""
        names = self.watchlist.all()
        if not names:
            print("\n  La watchlist esta vacia. Anade artistas con la opcion 3.\n")
            return

        print(f"\n  Analizando {len(names)} artistas de la watchlist...\n")
        results, errors = self.agent.analyze_many(names)

        for result in results:
            print(result.to_report())

        if results:
            print(
                render_summary_table(
                    [
                        {
                            "name": r.snapshot.name,
                            "followers": r.snapshot.followers,
                            "change_pct": r.trend.change_pct,
                            "direction": r.trend.direction,
                        }
                        for r in results
                    ]
                )
            )

        if errors:
            print("  INCIDENCIAS")
            for error in errors:
                print(f"   - {error}")
            print()

    def show_config(self) -> None:
        """Opcion 5: mostrar la configuracion vigente."""
        print("\n  CONFIGURACION ACTUAL")
        print("  " + "-" * 46)
        print(f"  Fuente de datos       : {self.agent.client.source_name}")
        print(f"  Metrica analizada     : {self.agent.metric}")
        print(f"  Ventana de analisis   : {config.ANALYSIS_WINDOW_DAYS} dias")
        print(f"  Minimo de puntos      : {config.MIN_SNAPSHOTS_FOR_TREND}")
        print(f"  Umbral de estabilidad : +/-{config.TREND_THRESHOLD_PCT}%")
        print(f"  Alerta por caida      : {config.ALERT_DROP_PCT}%")
        print(f"  Alerta por subida     : +{config.ALERT_SPIKE_PCT}%")
        print(f"  Instantaneas guardadas: {self.agent.store.total_snapshots()}")
        print(f"  Archivo de historico  : {config.SNAPSHOT_FILE}")
        print()

    def reset_history(self) -> None:
        """Opcion 6: borrar el historico, con confirmacion."""
        total = self.agent.store.total_snapshots()
        if total == 0:
            print("\n  No hay historico que borrar.\n")
            return

        answer = prompt_text(
            f"\n  Se borraran {total} instantaneas. Escribe SI para confirmar: "
        )
        if answer.upper() == "SI":
            self.agent.reset_history()
            print("  Historico borrado.\n")
        else:
            print("  Operacion cancelada.\n")

    # -- Bucle principal ------------------------------------------------------

    def run(self) -> int:
        """Bucle principal del menu. Devuelve el codigo de salida."""
        logger.info("Interfaz interactiva iniciada")
        actions = {
            1: self.analyze_one,
            2: self.show_catalog,
            3: self.manage_watchlist,
            4: self.analyze_watchlist,
            5: self.show_config,
            6: self.reset_history,
        }

        while True:
            print(
                MENU.format(
                    version=__version__, source=self.agent.client.source_name
                )
            )
            choice = prompt_int("  Opcion: ", set(actions) | {0})

            if choice == 0:
                print("\n  Hasta luego.\n")
                logger.info("Interfaz interactiva finalizada")
                return 0

            try:
                actions[choice]()
            except Exception:  # red de seguridad: el menu nunca debe morir
                logger.exception("Error no controlado en la opcion %d", choice)
                print("\n  ! Ocurrio un error inesperado. Revisa logs/app.log\n")


def run_demo(agent: FolkAnalyticsAgent | None = None) -> int:
    """Ejecucion no interactiva de demostracion.

    Recorre casos representativos, incluidos los de error, para que el
    comportamiento del agente pueda revisarse sin teclear nada.
    """
    agent = agent or FolkAnalyticsAgent()
    logger.info("Modo demostracion iniciado")

    queries = [
        "AURORA",              # artista en crecimiento
        "Novo Amor",           # crecimiento fuerte
        "The Paper Kites",     # en declive
        "vashti bunyan",       # declive leve, serie ruidosa
        "Hollow Pines",        # derrumbe -> alerta critica
        "",                    # entrada no valida
        "   ",                 # entrada no valida (solo espacios)
        "x" * 150,             # entrada demasiado larga
        "UNKNOWN ARTIST",      # sin actividad registrada
        "Bibio",               # no existe en el catalogo
    ]

    results, errors = agent.analyze_many(queries)

    for result in results:
        print(result.to_report())

    if results:
        print(
            render_summary_table(
                [
                    {
                        "name": r.snapshot.name,
                        "followers": r.snapshot.followers,
                        "change_pct": r.trend.change_pct,
                        "direction": r.trend.direction,
                    }
                    for r in results
                ]
            )
        )

    if errors:
        print("  INCIDENCIAS REGISTRADAS")
        print("  " + "-" * 46)
        for error in errors:
            print(f"   - {error}")
        print()

    logger.info("Modo demostracion finalizado")
    return 0
