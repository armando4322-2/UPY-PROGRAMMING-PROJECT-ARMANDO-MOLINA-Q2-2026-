#!/usr/bin/env python3
"""Generador de la interfaz web.

Toma las fuentes reales del paquete `folk_analytics` y las inyecta en la
plantilla `tools/web_template.html`, produciendo `docs/index.html`.

El motivo de que exista este script en lugar de escribir el HTML a mano es
evitar dos fuentes de verdad: la web ejecuta exactamente el mismo codigo que
la version de consola. Si el paquete cambia, se vuelve a ejecutar esto y la
web queda al dia.

Uso:
    python tools/build_web.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PACKAGE_DIR = PROJECT_ROOT / "folk_analytics"
TEMPLATE = PROJECT_ROOT / "tools" / "web_template.html"
OUTPUT = PROJECT_ROOT / "docs" / "index.html"

PLACEHOLDER = "/*__PYTHON_SOURCES__*/"
TESTS_DIR = PROJECT_ROOT / "tests"

# Modulos que no tienen sentido dentro del navegador.
EXCLUDED = {"__main__.py", "spotify.py"}


def collect_sources() -> dict[str, str]:
    """Lee todos los .py del paquete y los devuelve indexados por ruta."""
    sources: dict[str, str] = {}

    for path in sorted(PACKAGE_DIR.rglob("*.py")):
        if path.name in EXCLUDED:
            continue
        relative = path.relative_to(PROJECT_ROOT).as_posix()
        sources[relative] = path.read_text(encoding="utf-8")

    if not sources:
        raise SystemExit("No se encontro ningun modulo de folk_analytics")

    return sources


def count_tests() -> int:
    """Cuenta las funciones de test declaradas en tests/.

    Evita que la cifra que muestra la web se escriba a mano y quede obsoleta
    en cuanto se anada un test.
    """
    import ast

    total = 0
    for path in TESTS_DIR.glob("test_*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
                total += 1
    return total


def build() -> Path:
    """Genera docs/index.html a partir de la plantilla."""
    if not TEMPLATE.exists():
        raise SystemExit(f"Falta la plantilla: {TEMPLATE}")

    sources = collect_sources()

    # `</script>` dentro de una cadena JSON cerraria la etiqueta antes de tiempo.
    payload = json.dumps(sources, ensure_ascii=False).replace("</", "<\\/")

    html = TEMPLATE.read_text(encoding="utf-8")
    if PLACEHOLDER not in html:
        raise SystemExit(f"La plantilla no contiene el marcador {PLACEHOLDER}")

    tests = count_tests()
    html = html.replace(
        PLACEHOLDER,
        f"const PYTHON_SOURCES = {payload};\n"
        f"const TEST_COUNT = {tests};",
    )

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(html, encoding="utf-8")

    total_lines = sum(src.count("\n") for src in sources.values())
    print(f"  Modulos inyectados : {len(sources)}")
    for name in sources:
        print(f"    - {name}")
    print(f"  Lineas de Python   : {total_lines:,}")
    print(f"  Tests contados     : {tests}")
    print(f"  Generado           : {OUTPUT.relative_to(PROJECT_ROOT)}")
    print(f"  Tamano             : {OUTPUT.stat().st_size / 1024:.1f} KB")
    return OUTPUT


if __name__ == "__main__":
    try:
        build()
    except SystemExit as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise
