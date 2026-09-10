"""Capa de extracción: todo lo que toca pdfplumber vive aquí.

Responsabilidad única: convertir una página PDF en una matriz de celdas
limpias y localizar dentro de ella el encabezado y el bloque de detalle.
"""

from __future__ import annotations
from .config import (
    ETIQUETA_CODIGO,
    ETIQUETA_COLOCAR,
    ETIQUETA_DESCRIPCION,
    ETIQUETA_QUITAR,
)
from .texto import limpiar_celda, quitar_tildes

Tabla = list[list[str]]
MapaColumnas = dict[str, int]



def detectar_tabla(pagina) -> Tabla | None:
    """Devuelve la tabla de la página como matriz de strings limpios.

    Se queda con la tabla que contenga la columna 'Colocar', que es la firma
    del formato UCAP. Devuelve None si la página no tiene ese formato.
    """
    mejor: Tabla | None = None

    for cruda in pagina.extract_tables() or []:
        if not cruda:
            continue
        tabla = [[limpiar_celda(c) for c in fila] for fila in cruda]
        tiene_firma = any(
            "COLOCAR" in quitar_tildes(c).upper()
            for fila in tabla
            for c in fila
        )
        if tiene_firma and (mejor is None or len(tabla) > len(mejor)):
            mejor = tabla

    return mejor

def localizar_encabezado(tabla: Tabla) -> tuple[int | None, MapaColumnas | None]:
    """Ubica la fila de encabezados de columna y mapea sus índices.

    Devuelve (indice_fila, {'codigo': 0, 'descripcion': 1, ...}) o
    (None, None) si la página no tiene el formato esperado.

    Los índices se buscan por el nombre del encabezado, nunca se hardcodean:
    si el formato agrega una columna, el parser sobrevive en vez de desplazar
    todos los datos en silencio.
    """
    for indice, fila in enumerate(tabla):
        celdas = [quitar_tildes(c).upper() for c in fila]

        tiene_ambas = (
            any(ETIQUETA_COLOCAR in c for c in celdas)
            and any(ETIQUETA_QUITAR in c for c in celdas)
        )
        if not tiene_ambas:
            continue

        mapa: MapaColumnas = {}
        for j, celda in enumerate(celdas):
            if ETIQUETA_CODIGO in celda and "codigo" not in mapa:
                mapa["codigo"] = j
            elif ETIQUETA_DESCRIPCION in celda and "descripcion" not in mapa:
                mapa["descripcion"] = j
            elif ETIQUETA_COLOCAR in celda and "colocar" not in mapa:
                mapa["colocar"] = j
            elif ETIQUETA_QUITAR in celda and "quitar" not in mapa:
                mapa["quitar"] = j

        if {"colocar", "quitar"} <= mapa.keys():
            mapa.setdefault("codigo", 0)
            mapa.setdefault("descripcion", 1)
            return indice, mapa

    return None, None