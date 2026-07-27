#!/usr/bin/env python3
"""Lanzador del proyecto.

Equivalente a `python -m folk_analytics`, pensado para quien prefiera
ejecutar un archivo suelto:

    python run.py --demo
"""

import sys

from folk_analytics.__main__ import main

if __name__ == "__main__":
    sys.exit(main())
