"""Punto de entrada del proyecto.

Uso:
    python main.py data/raw/archivo.pdf -o data/processed/ucap_historico.csv
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from ucap_etl.cli import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())