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
    RE_NUMERO_DOCUMENTO,
    RE_TIPO_DOCUMENTO,
)
from .modelos import ContextoPagina
from .texto import limpiar_celda, quitar_tildes

Tabla = list[list[str]]
MapaColumnas = dict[str, int]

def _tiene_filas_mutiladas(tabla: Tabla) -> bool:
    """True si alguna fila trae cantidad pero perdió código y descripción.

    Es el síntoma de que a la cuadrícula del PDF le faltó un borde y
    pdfplumber descartó el texto de las celdas que quedaron sin cerrar.
    """
    for fila in tabla:
        if len(fila) < 4:
            continue
        sin_identificacion = not fila[0] and not fila[1]
        con_cantidad = bool(fila[2]) or bool(fila[3])
        if sin_identificacion and con_cantidad:
            return True
    return False

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

    if mejor is None:
        return _tabla_por_coordenadas(pagina)

    if _tiene_filas_mutiladas(mejor):
        respaldo = _tabla_por_coordenadas(pagina)
        if respaldo is not None and not _tiene_filas_mutiladas(respaldo):
            return respaldo

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


def extraer_contexto(tabla: Tabla) -> ContextoPagina:
    """Obtiene proyecto, tipo (SS/SN) y número del encabezado de la hoja.

    Recorre las celdas buscando la etiqueta 'Proyecto' y el literal SS/SN.
    El nombre del proyecto es la primera celda no vacía a la derecha de la
    etiqueta; el número, la primera celda a la derecha del tipo que cumpla
    el patrón de documento.
    """
    proyecto = ""
    tipo = ""
    numero = ""

    for fila in tabla:
        for j, celda in enumerate(fila):
            if not proyecto and quitar_tildes(celda).upper().startswith("PROYECTO"):
                for k in range(j + 1, len(fila)):
                    candidato = fila[k]
                    if candidato and not RE_TIPO_DOCUMENTO.match(candidato):
                        proyecto = candidato
                        break

            if not tipo and RE_TIPO_DOCUMENTO.match(celda):
                tipo = celda.upper()
                for k in range(j + 1, len(fila)):
                    if RE_NUMERO_DOCUMENTO.match(fila[k]):
                        numero = fila[k]
                        break

        if proyecto and tipo and numero:
            break
            
    return ContextoPagina(
        proyecto=proyecto.strip(" ,;"),
        tipo=tipo,
        numero=numero,
    )
    
def _columnas_de_pagina(pagina, tolerancia: int = 3) -> list[float] | None:
    """Deduce los cortes de columna de la geometría del PDF.

    Algunas páginas dibujan la cuadrícula con líneas y otras solo con
    rectángulos, así que se consideran ambas fuentes. Las coordenadas varían
    uno o dos puntos entre páginas, de modo que las cercanas se agrupan en
    un solo corte.
    """
    xs = set()
    for objeto in list(pagina.lines) + list(pagina.rects):
        xs.add(round(objeto["x0"]))
        xs.add(round(objeto["x1"]))

    if not xs:
        return None

    cortes = [min(xs)]
    for x in sorted(xs):
        if x - cortes[-1] > tolerancia:
            cortes.append(x)

    return [float(x) for x in cortes] if len(cortes) >= 4 else None

def _filas_de_pagina(pagina, margen: float = 7.0) -> list[float] | None:
    """Deduce los cortes de fila a partir del top de cada palabra.

    Cada fila del formato ocupa una banda vertical propia, así que basta
    con tomar los tops distintos y abrir un margen arriba y abajo.
    """
    tops = sorted({round(w["top"], 1) for w in pagina.extract_words()})
    if len(tops) < 2:
        return None
    return [t - margen for t in tops] + [tops[-1] + margen]

def _tabla_por_coordenadas(pagina) -> Tabla | None:
    """Reconstruye la tabla usando cortes explícitos de fila y columna.

    Necesario cuando al formato le falta algún borde de celda: pdfplumber
    descarta el texto de las celdas que no quedan cerradas, y así se pierden
    filas completas que sí están en el documento.
    """
    columnas = _columnas_de_pagina(pagina)
    filas = _filas_de_pagina(pagina)
    if not columnas or not filas:
        return None

    cfg = {
        "vertical_strategy": "explicit",
        "explicit_vertical_lines": columnas,
        "horizontal_strategy": "explicit",
        "explicit_horizontal_lines": filas,
    }
    try:
        tablas = pagina.extract_tables(cfg)
    except Exception:
        return None

    for cruda in tablas or []:
        if cruda:
            return [[limpiar_celda(c) for c in fila] for fila in cruda]
    return None