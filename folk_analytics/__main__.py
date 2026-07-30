"""Punto de entrada del paquete.

Permite ejecutar el agente con:

    python -m folk_analytics             # menu interactivo
    python -m folk_analytics --demo      # demostracion no interactiva
    python -m folk_analytics -a AURORA   # analisis directo de un artista
"""

from __future__ import annotations

import argparse
import logging
import sys

from folk_analytics import __version__
from folk_analytics.agent import FolkAnalyticsAgent, InvalidInputError
from folk_analytics.api.base import ArtistNotFoundError, StreamingAPIError
from folk_analytics.logging_setup import setup_logging


def build_parser() -> argparse.ArgumentParser:
    """Construye el parser de argumentos de linea de comandos."""
    parser = argparse.ArgumentParser(
        prog="folk-analytics",
        description="Agente de inteligencia de streaming para artistas musicales.",
    )
    parser.add_argument(
        "--version", action="version", version=f"Folk Analytics {__version__}"
    )
    parser.add_argument(
        "-a", "--artist", help="analiza un artista concreto y termina"
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="ejecuta una demostracion no interactiva con casos de prueba",
    )
    parser.add_argument(
        "--source",
        choices=["simulated", "deezer", "spotify"],
        default="simulated",
        help=(
            "fuente de datos. 'simulated' trae historico completo y sirve para "
            "demostrar la deteccion de tendencias; 'deezer' son datos reales sin "
            "credenciales; 'spotify' son datos reales pero requiere credenciales "
            "en .env (por defecto: simulated)"
        ),
    )
    parser.add_argument(
        "--metric",
        choices=["followers", "monthly_listeners", "popularity"],
        default="followers",
        help="metrica sobre la que se calcula la tendencia",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="muestra logs de depuracion"
    )
    parser.add_argument(
        "-q", "--quiet", action="store_true", help="oculta los logs en consola"
    )
    return parser


def build_client(source: str):
    """Instancia el cliente de datos elegido, con degradacion elegante."""
    if source == "deezer":
        from folk_analytics.api.deezer import DeezerClient

        return DeezerClient()

    if source == "spotify":
        from folk_analytics.api.spotify import SpotifyClient

        try:
            return SpotifyClient()
        except StreamingAPIError as exc:
            print(f"\n  ! No se pudo usar la API de Spotify: {exc}")
            print("    Se continuara con datos simulados.\n")

    from folk_analytics.api.simulated import SimulatedClient

    return SimulatedClient()


def main(argv: list[str] | None = None) -> int:
    """Punto de entrada principal."""
    args = build_parser().parse_args(argv)

    if args.quiet:
        level = logging.CRITICAL
    elif args.verbose:
        level = logging.DEBUG
    else:
        level = logging.INFO

    setup_logging(level=level)

    agent = FolkAnalyticsAgent(client=build_client(args.source), metric=args.metric)

    if args.demo:
        from folk_analytics.cli import run_demo

        return run_demo(agent)

    if args.artist:
        try:
            print(agent.analyze(args.artist).to_report())
        except InvalidInputError as exc:
            print(f"\n  ! Entrada no valida: {exc}\n")
            return 2
        except ArtistNotFoundError:
            print(f"\n  ! No se encontro el artista '{args.artist}'.\n")
            return 3
        except StreamingAPIError as exc:
            print(f"\n  ! La fuente de datos fallo: {exc}\n")
            return 4
        return 0

    from folk_analytics.cli import FolkAnalyticsCLI

    return FolkAnalyticsCLI(agent).run()


if __name__ == "__main__":
    sys.exit(main())
