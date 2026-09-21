"""Lógica de negocio a nivel de página: de tabla cruda a registros UCAP."""

from __future__ import annotations

from dataclasses import dataclass, field

from .extraccion import detectar_tabla, extraer_contexto, localizar_encabezado
from .modelos import ContextoPagina, RegistroUCAP
from .texto import construir_fuente, es_codigo_ucap, extraer_anio, parsear_cantidad


@dataclass
class ResultadoPagina:
    """Salida de procesar una página: registros, contexto e incidencias."""

    registros: list[RegistroUCAP] = field(default_factory=list)
    contexto: ContextoPagina = field(default_factory=ContextoPagina)
    incidencias: list[str] = field(default_factory=list)
    
    
def _es_fila_de_relleno(codigo: str, descripcion: str, colocar, quitar) -> bool:
    """El formato trae filas en blanco al final de cada hoja.

    Se descartan en silencio porque son parte del diseño del documento, no
    datos faltantes.
    """
    sin_cantidad = colocar in (None, 0) and quitar in (None, 0)
    return not codigo and not descripcion and sin_cantidad

def _leer(fila: list[str], mapa: dict[str, int], clave: str) -> str:
    """Lee una celda por nombre lógico, tolerando filas más cortas."""
    indice = mapa[clave]
    return fila[indice] if indice < len(fila) else ""


def _debe_heredar(contexto: ContextoPagina, previo: ContextoPagina) -> bool:
    """Una página hereda el encabezado anterior solo si no trae ni proyecto
    ni número propios.

    Si trae cualquiera de los dos es un documento distinto, y sus datos
    faltantes se reportan, nunca se rellenan con los de otra hoja. Casos
    reales que fijan la regla:
      - Telegestión (validación 2026, pág 132): nombre partido que no se leyó
        completo, pero con número propio. No hereda.
      - Página 98 de 2026: proyecto propio y número en cero en el origen.
        No hereda; se reporta como encabezado incompleto.
    """
    return not contexto.proyecto and not contexto.numero and previo.esta_completo

def procesar_pagina(
    pagina,
    numero_pagina: int,
    nombre_archivo: str,
    contexto_previo: ContextoPagina,
    cantidades_en_cero: bool = False,
) -> ResultadoPagina:
    """Convierte una página del PDF en registros UCAP.

    contexto_previo permite heredar el encabezado cuando un proyecto se
    extiende a una segunda hoja sin repetir la cabecera.
    """
    resultado = ResultadoPagina(contexto=contexto_previo)

    tabla = detectar_tabla(pagina)
    if tabla is None:
        resultado.incidencias.append(f"pág {numero_pagina}: no se detectó tabla")
        return resultado

    indice_encabezado, mapa = localizar_encabezado(tabla)
    if indice_encabezado is None or mapa is None:
        resultado.incidencias.append(
            f"pág {numero_pagina}: no se detectó la fila de encabezados"
        )
        return resultado

    contexto = extraer_contexto(tabla[: indice_encabezado + 1])

    if _debe_heredar(contexto, contexto_previo):
        contexto = contexto_previo
        resultado.incidencias.append(
            f"pág {numero_pagina}: sin encabezado propio, hereda {contexto.documento}"
        )
    elif not contexto.esta_completo:
        resultado.incidencias.append(
            f"pág {numero_pagina}: encabezado incompleto "
            f"(proyecto={contexto.proyecto!r}, tipo={contexto.tipo!r}, "
            f"numero={contexto.numero!r})"
        )

    resultado.contexto = contexto
    fuente = construir_fuente(nombre_archivo, numero_pagina)
    
    anio = extraer_anio(nombre_archivo)
    if not anio:
        resultado.incidencias.append(
            f"pág {numero_pagina}: no se pudo determinar el año desde "
            f"el nombre del archivo {nombre_archivo!r}"
        )

    for fila in tabla[indice_encabezado + 1:]:
        codigo_crudo = _leer(fila, mapa, "codigo")
        descripcion = _leer(fila, mapa, "descripcion")
        colocar = parsear_cantidad(_leer(fila, mapa, "colocar"), cantidades_en_cero)
        quitar = parsear_cantidad(_leer(fila, mapa, "quitar"), cantidades_en_cero)

        if _es_fila_de_relleno(codigo_crudo, descripcion, colocar, quitar):
            continue

        if not codigo_crudo and not descripcion:
            resultado.incidencias.append(
                f"pág {numero_pagina}: fila con cantidad pero sin descripción ni código"
            )
            continue

        codigo = codigo_crudo if es_codigo_ucap(codigo_crudo) else ""
        if codigo_crudo and not codigo:
            resultado.incidencias.append(
                f"pág {numero_pagina}: código no reconocido {codigo_crudo!r} "
                f"en '{descripcion}'"
            )

        registro = RegistroUCAP(
            pagina=numero_pagina,
            anio=anio,
            contexto=contexto,
            codigo=codigo,
            descripcion=descripcion,
            colocar=colocar,
            quitar=quitar,
            fuente=fuente,
        )

        if registro.movimiento == "NULO":
            resultado.incidencias.append(
                f"pág {numero_pagina}: '{descripcion}' se descarta porque no tiene cantidad de colocar ni quitar"
            )
            continue

        resultado.registros.append(registro)

    if not resultado.registros:
        resultado.incidencias.append(f"pág {numero_pagina}: 0 registros extraídos")

    return resultado