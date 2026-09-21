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
from .texto import quitar_tildes

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

def _archivo_de_fuente(fuente: str) -> str:
    """'Tablas 1 al 392_2025.pdf, pagina 7' -> 'Tablas 1 al 392_2025.pdf'."""
    return str(fuente).rsplit(", pagina", 1)[0]


def _proyecto_comparable(texto: object) -> str:
    """Nombre de proyecto normalizado para comparar entre páginas."""
    t = quitar_tildes(str(texto or "")).upper()
    return " ".join(t.replace(",", " ").split())


def resolver_paginas_duplicadas(
    datos: pd.DataFrame,
) -> tuple[pd.DataFrame, list[str]]:
    """Cuando un mismo documento aparece en varias páginas del mismo archivo,
    conserva la página con mayor suma de Colocar.

    Duplicado significa mismo SS/SN y mismo proyecto dentro de un archivo.
    Cada archivo se evalúa solo contra sí mismo.

    Si un SS/SN se repite con proyectos distintos no es duplicación sino un
    probable error de digitación del número: se conservan todas las páginas
    y se reporta para corregirlo en el origen.

    En empate gana la página de menor número. Cada descarte queda reportado.
    """
    if datos.empty:
        return datos, []

    trabajo = datos.copy()
    trabajo["_archivo"] = trabajo["Fuente"].map(_archivo_de_fuente)
    trabajo["_pagina"] = pd.to_numeric(trabajo["Pagina"], errors="coerce")
    trabajo["_colocar"] = pd.to_numeric(trabajo["Colocar"], errors="coerce").fillna(0)
    trabajo["_proyecto"] = trabajo["Proyecto"].map(_proyecto_comparable)

    con_numero = trabajo["SS/SN"].fillna("").astype(str).str.strip() != ""

    por_pagina = (
        trabajo[con_numero]
        .groupby(["_archivo", "SS/SN", "_proyecto", "_pagina"], as_index=False)
        .agg(colocar=("_colocar", "sum"), items=("_colocar", "size"))
    )

    incidencias: list[str] = []

    # Mismo número con proyectos distintos: se reporta, no se toca.
    for (archivo, documento), grupo in por_pagina.groupby(["_archivo", "SS/SN"]):
        if grupo["_proyecto"].nunique() > 1:
            paginas = ", ".join(str(int(p)) for p in sorted(grupo["_pagina"]))
            incidencias.append(
                f"{archivo}: el documento {documento} aparece con proyectos "
                f"distintos en las págs {paginas}; posible error de digitación "
                f"del número, se conservan todas"
            )

    # Mismo número y mismo proyecto: se conserva la de mayor Colocar.
    descartar: set[tuple[str, float]] = set()
    for (archivo, documento, _), grupo in por_pagina.groupby(
        ["_archivo", "SS/SN", "_proyecto"]
    ):
        if len(grupo) < 2:
            continue
        orden = grupo.sort_values(["colocar", "_pagina"], ascending=[False, True])
        ganadora = orden.iloc[0]
        for _, perdedora in orden.iloc[1:].iterrows():
            descartar.add((archivo, perdedora["_pagina"]))
            incidencias.append(
                f"{archivo} pág {int(perdedora['_pagina'])}: se descarta por duplicar "
                f"el documento {documento} ({int(perdedora['items'])} ítems, "
                f"colocar {perdedora['colocar']:g}); se conserva la pág "
                f"{int(ganadora['_pagina'])} ({int(ganadora['items'])} ítems, "
                f"colocar {ganadora['colocar']:g})"
            )

    if not descartar:
        return datos, incidencias

    mascara = [
        (archivo, pagina) not in descartar
        for archivo, pagina in zip(trabajo["_archivo"], trabajo["_pagina"])
    ]
    return datos[mascara].reset_index(drop=True), incidencias

def ejecutar(
    rutas: list[Path],
    ruta_salida: Path,
    modo_append: bool = False,
    cantidades_en_cero: bool = False,
) -> ResultadoExtraccion:
    """Punto de entrada del pipeline completo."""
    resultado = extraer_lote(rutas, cantidades_en_cero)

    depurados, descartes = resolver_paginas_duplicadas(resultado.datos)
    incidencias = resultado.incidencias + descartes

    datos = (
        fusionar_con_historico(depurados, ruta_salida)
        if modo_append
        else a_texto_csv(depurados)
    )

    escribir_csv(datos, ruta_salida)
    return ResultadoExtraccion(datos=datos, incidencias=incidencias)