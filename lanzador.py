"""Lanzador para usuarios finales: doble clic y listo.

Procesa todos los PDF de la carpeta PDF_entrada y regenera el histórico
completo en CSV_salida. Pensado para correr sin terminal ni argumentos.
"""

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from ucap_etl.calidad import reportar  # noqa: E402
from ucap_etl.config import RAIZ_PROYECTO  # noqa: E402
from ucap_etl.pipeline import ejecutar  # noqa: E402
from ucap_etl.texto import extraer_anio  # noqa: E402

DIR_ENTRADA = RAIZ_PROYECTO / "PDF_entrada"
DIR_SALIDA = RAIZ_PROYECTO / "CSV_salida"
DIR_LOGS = RAIZ_PROYECTO / "logs"
RUTA_CSV = DIR_SALIDA / "ucap_historico.csv"


def configurar_logging() -> None:
    DIR_LOGS.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(DIR_LOGS / "ejecucion.log", mode="w", encoding="utf-8"),
        ],
    )


def main() -> int:
    for carpeta in (DIR_ENTRADA, DIR_SALIDA, DIR_LOGS):
        carpeta.mkdir(parents=True, exist_ok=True)

    pdfs = sorted(DIR_ENTRADA.glob("*.pdf"))
    if not pdfs:
        print(f"No hay archivos PDF en:\n  {DIR_ENTRADA}")
        print("\nCopie ahí los PDF y vuelva a ejecutar.")
        return 1

    sin_anio = [p.name for p in pdfs if not extraer_anio(p.name)]
    if sin_anio:
        print("Estos archivos no tienen el año en el nombre:\n")
        for nombre in sin_anio:
            print(f"  {nombre}")
        print("\nRenómbrelos agregando el año, por ejemplo:")
        print("  UCAP EN VALIDACION DE APROBACION_2026.pdf")
        print("\nNo se procesó nada.")
        return 1

    print(f"Procesando {len(pdfs)} archivo(s). Los ya procesados se reutilizan.\n")

    try:
        resultado = ejecutar(rutas=pdfs, ruta_salida=RUTA_CSV)
    except PermissionError:
        print(f"\nNo se pudo escribir:\n  {RUTA_CSV}")
        print("\nProbablemente está abierto en Excel. Ciérrelo y vuelva a ejecutar.")
        return 1

    reportar(
        resultado.datos,
        resultado.incidencias,
        DIR_LOGS / "ucap_historico.incidencias.log",
    )

    print("\n" + "=" * 60)
    print(f"Listo. {len(resultado.datos)} registros generados.")
    print(f"CSV:         {RUTA_CSV}")
    print(f"Incidencias: {DIR_LOGS / 'ucap_historico.incidencias.log'}")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    configurar_logging()
    try:
        codigo = main()
    except Exception:
        logging.exception("Error inesperado. Envíe logs/ejecucion.log a soporte.")
        codigo = 1
    input("\nPresione Enter para cerrar...")
    sys.exit(codigo)