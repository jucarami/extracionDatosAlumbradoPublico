"""Orquestación del ETL: PDF hacia DataFrame hacia CSV histórico."""

from __future__ import annotations

import csv
import logging
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd
import pdfplumber

from .config import CLAVE_DEDUPLICACION, COLUMNAS_SALIDA
from .modelos import ContextoPagina
from .paginas import procesar_pagina

log = logging.getLogger(__name__)


@dataclass
class ResultadoExtraccion:
    """Salida del pipeline: los datos y todo lo que hubo que reportar."""

    datos: pd.DataFrame
    incidencias: list[str] = field(default_factory=list)
    
def extraer_pdf(ruta_pdf: Path, cantidades_en_cero: bool = False) -> ResultadoExtraccion:
    """Recorre todas las páginas de un PDF y devuelve sus registros."""
    filas: list[dict[str, object]] = []
    incidencias: list[str] = []
    contexto = ContextoPagina()

    with pdfplumber.open(ruta_pdf) as pdf:
        total = len(pdf.pages)
        log.info("%s: %d páginas", ruta_pdf.name, total)

        for numero, pagina in enumerate(pdf.pages, start=1):
            resultado = procesar_pagina(
                pagina=pagina,
                numero_pagina=numero,
                nombre_archivo=ruta_pdf.name,
                contexto_previo=contexto,
                cantidades_en_cero=cantidades_en_cero,
            )
            contexto = resultado.contexto
            incidencias.extend(resultado.incidencias)
            filas.extend(registro.a_dict() for registro in resultado.registros)

            if numero % 50 == 0 or numero == total:
                log.info("  %d/%d páginas, %d filas", numero, total, len(filas))

    datos = pd.DataFrame(filas, columns=list(COLUMNAS_SALIDA))
    return ResultadoExtraccion(datos=datos, incidencias=incidencias)


def _formatear_cantidad(valor: object) -> str:
    """Evita que pandas escriba '4.0' donde el formato dice '4'.

    Al mezclar enteros con nulos, pandas promueve la columna a float. Se
    formatea a texto explícitamente para que el histórico quede limpio.
    """
    if valor is None or valor == "" or (isinstance(valor, float) and pd.isna(valor)):
        return ""
    if isinstance(valor, str):
        return valor
    numero = float(valor)
    return str(int(numero)) if numero.is_integer() else str(numero)


def a_texto_csv(datos: pd.DataFrame) -> pd.DataFrame:
    """Proyecta el DataFrame a texto plano, listo para persistir o comparar."""
    salida = datos.reindex(columns=list(COLUMNAS_SALIDA)).copy()
    for columna in ("Colocar", "Quitar"):
        salida[columna] = salida[columna].map(_formatear_cantidad)
    for columna in salida.columns:
        if columna not in ("Colocar", "Quitar"):
            salida[columna] = salida[columna].fillna("").astype(str)
    return salida


def escribir_csv(datos: pd.DataFrame, ruta_salida: Path) -> Path:
    """Persiste el histórico respetando el orden de columnas del esquema."""
    ruta_salida.parent.mkdir(parents=True, exist_ok=True)
    datos = a_texto_csv(datos)
    datos.to_csv(
        ruta_salida,
        index=False,
        encoding="utf-8-sig",
        quoting=csv.QUOTE_MINIMAL,
        na_rep="",
    )
    log.info("CSV escrito: %s (%d filas)", ruta_salida, len(datos))
    return ruta_salida  

def extraer_lote(rutas: list[Path], cantidades_en_cero: bool = False) -> ResultadoExtraccion:
    """Procesa varios PDF y concatena sus resultados."""
    marcos: list[pd.DataFrame] = []
    incidencias: list[str] = []

    for ruta in rutas:
        resultado = extraer_pdf(ruta, cantidades_en_cero)
        marcos.append(resultado.datos)
        incidencias.extend(resultado.incidencias)

    datos = (
        pd.concat(marcos, ignore_index=True)
        if marcos
        else pd.DataFrame(columns=list(COLUMNAS_SALIDA))
    )
    return ResultadoExtraccion(datos=datos, incidencias=incidencias)


def fusionar_con_historico(nuevos: pd.DataFrame, ruta_csv: Path) -> pd.DataFrame:
    """Agrega los nuevos registros al CSV existente, deduplicando."""
    nuevos = a_texto_csv(nuevos)
    if not ruta_csv.exists():
        return nuevos

    previos = pd.read_csv(ruta_csv, dtype=str, keep_default_na=False)
    combinados = pd.concat([previos, nuevos], ignore_index=True)
    antes = len(combinados)
    combinados = combinados.drop_duplicates(subset=list(CLAVE_DEDUPLICACION))
    log.info("Append: %d filas, %d tras deduplicar", antes, len(combinados))
    return combinados


def ejecutar(
    rutas: list[Path],
    ruta_salida: Path,
    modo_append: bool = False,
    cantidades_en_cero: bool = False,
) -> ResultadoExtraccion:
    """Punto de entrada del pipeline completo."""
    resultado = extraer_lote(rutas, cantidades_en_cero)

    datos = (
        fusionar_con_historico(resultado.datos, ruta_salida)
        if modo_append
        else a_texto_csv(resultado.datos)
    )

    escribir_csv(datos, ruta_salida)
    return ResultadoExtraccion(datos=datos, incidencias=resultado.incidencias)