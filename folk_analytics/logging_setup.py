"""Configuracion del sistema de logging.

Escribe a archivo (UTF-8) y a consola. La consola usa un formato mas corto
y degrada a ASCII si la terminal no soporta Unicode (caso tipico: cmd.exe
en Windows con codepage 850/1252).
"""

import logging
import sys

from folk_analytics import config

_CONFIGURED = False


def _console_supports_unicode() -> bool:
    """Detecta si stdout puede escribir caracteres Unicode sin reventar."""
    encoding = getattr(sys.stdout, "encoding", None) or ""
    try:
        "─\U0001F4C8".encode(encoding)
        return True
    except (UnicodeEncodeError, LookupError):
        return False


CONSOLE_UNICODE = _console_supports_unicode()


class _SafeConsoleFormatter(logging.Formatter):
    """Formatter que reemplaza caracteres no representables en vez de fallar."""

    def format(self, record: logging.LogRecord) -> str:
        text = super().format(record)
        if not CONSOLE_UNICODE:
            text = text.encode("ascii", errors="replace").decode("ascii")
        return text


def setup_logging(level: int = logging.INFO, verbose_file: bool = True) -> logging.Logger:
    """Inicializa el logging del proyecto. Es idempotente."""
    global _CONFIGURED

    logger = logging.getLogger("folk_analytics")

    if _CONFIGURED:
        return logger

    config.LOG_DIR.mkdir(parents=True, exist_ok=True)

    logger.setLevel(logging.DEBUG)
    logger.propagate = False

    file_handler = logging.FileHandler(config.LOG_FILE, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG if verbose_file else logging.INFO)
    file_handler.setFormatter(
        logging.Formatter(
            "%(asctime)s - [%(levelname)-8s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(
        _SafeConsoleFormatter("[%(levelname)-8s] %(message)s")
    )

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    _CONFIGURED = True
    logger.debug("Sistema de logging inicializado")
    return logger


def get_logger(name: str) -> logging.Logger:
    """Devuelve un logger hijo del logger raiz del proyecto."""
    return logging.getLogger(f"folk_analytics.{name}")
