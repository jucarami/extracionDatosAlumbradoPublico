"""Interfaz de línea de comandos. Única capa que arma la configuración."""

from __future__ import annotations

import argparse
import glob
import logging
import sys
from pathlib import Path

import pdfplumber

from .calidad import reportar, resumen_por_documento
from .config import DIR_LOGS, DIR_PROCESSED
from .extraccion import detectar_tabla, extraer_contexto, localizar_encabezado
from .pipeline import ejecutar

log = logging.getLogger("ucap_etl")


def configurar_logging(verboso: bool = False) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verboso else logging.INFO,
        format="%(levelname)-8s %(message)s",
        stream=sys.stdout,
    )


def resolver_rutas(patron: str) -> list[Path]:
    """Acepta una ruta concreta o un patrón glob."""
    encontradas = sorted(Path(p) for p in glob.glob(patron))
    if encontradas:
        return encontradas
    ruta = Path(patron)
    if ruta.exists():
        return [ruta]
    raise FileNotFoundError(f"No se encontró ningún PDF con el patrón: {patron}")

def depurar_pagina(ruta_pdf: Path, numero_pagina: int) -> None:
    """Inspecciona una página para ajustar el parser antes del lote completo."""
    with pdfplumber.open(ruta_pdf) as pdf:
        pagina = pdf.pages[numero_pagina - 1]

        print("=== TEXTO PLANO ===")
        print(pagina.extract_text())

        print("\n=== TABLA DETECTADA ===")
        tabla = detectar_tabla(pagina)
        if tabla is None:
            print("Ninguna estrategia detectó tabla en esta página.")
            return
        for indice, fila in enumerate(tabla):
            print(indice, fila)

        indice_encabezado, mapa = localizar_encabezado(tabla)
        print("\nFila de encabezados:", indice_encabezado)
        print("Mapa de columnas:   ", mapa)
        print("Contexto:           ", extraer_contexto(tabla))
        
def construir_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ucap-etl",
        description="Extrae los formatos UCAP AP de un PDF a un CSV histórico.",
    )
    parser.add_argument("pdf", help="Ruta del PDF o patrón glob ('data/raw/*.pdf')")
    parser.add_argument(
        "-o", "--out",
        default=str(DIR_PROCESSED / "ucap_historico.csv"),
        help="Ruta del CSV de salida",
    )
    parser.add_argument(
        "--append", action="store_true",
        help="Agrega al CSV existente en lugar de reemplazarlo",
    )
    parser.add_argument(
        "--ceros", action="store_true",
        help="Escribe 0 en Colocar/Quitar vacíos en vez de dejar la celda vacía",
    )
    parser.add_argument(
        "--debug", type=int, metavar="N",
        help="Inspecciona la página N del primer PDF y termina",
    )
    parser.add_argument(
        "--resumen", action="store_true",
        help="Imprime los totales por documento para conciliar contra el PDF",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    return parser

def main(argv: list[str] | None = None) -> int:
    args = construir_parser().parse_args(argv)
    configurar_logging(args.verbose)

    try:
        rutas = resolver_rutas(args.pdf)
    except FileNotFoundError as error:
        log.error("%s", error)
        return 1

    if args.debug:
        depurar_pagina(rutas[0], args.debug)
        return 0

    salida = Path(args.out)
    resultado = ejecutar(
        rutas=rutas,
        ruta_salida=salida,
        modo_append=args.append,
        cantidades_en_cero=args.ceros,
    )

    reportar(
        resultado.datos,
        resultado.incidencias,
        DIR_LOGS / f"{salida.stem}.incidencias.log",
    )

    if args.resumen:
        print("\n=== Totales por documento ===")
        print(resumen_por_documento(resultado.datos).to_string(index=False))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())