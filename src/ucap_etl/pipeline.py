"""Orquestación del ETL: PDF hacia DataFrame hacia CSV histórico."""

from __future__ import annotations

import csv
import logging
import json
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd
import pdfplumber

from .config import CLAVE_DEDUPLICACION, COLUMNAS_SALIDA, RUTA_CORRECCIONES, DIR_CACHE, VERSION_EXTRACCION
from .modelos import ContextoPagina
from .paginas import procesar_pagina
from .texto import normalizar_descripcion ,quitar_tildes

log = logging.getLogger(__name__)


@dataclass
class ResultadoExtraccion:
    """Salida del pipeline: los datos y todo lo que hubo que reportar."""

    datos: pd.DataFrame
    incidencias: list[str] = field(default_factory=list)
    
def _firma_archivo(ruta: Path) -> str:
    """Identifica la versión de un PDF por su nombre, tamaño y fecha.

    Si cualquiera de los tres cambia, el archivo se reprocesa. Es más rápido
    que un hash del contenido y suficiente para detectar un PDF reemplazado.
    """
    info = ruta.stat()
    return f"{ruta.name}|{info.st_size}|{int(info.st_mtime)}"


def _rutas_cache(ruta_pdf: Path, dir_cache: Path) -> tuple[Path, Path]:
    """Archivos de caché de un PDF: sus filas y sus metadatos."""
    base = "".join(c if c.isalnum() else "_" for c in ruta_pdf.stem)[:80]
    return dir_cache / f"{base}.csv", dir_cache / f"{base}.json"


def _leer_cache(ruta_pdf: Path, dir_cache: Path) -> ResultadoExtraccion | None:
    """Devuelve la extracción cacheada si el PDF no ha cambiado.

    El caché se descarta también cuando cambia la versión de extracción, para
    que un ajuste en las reglas no quede escondido detrás de datos viejos.
    """
    ruta_filas, ruta_meta = _rutas_cache(ruta_pdf, dir_cache)
    if not ruta_filas.exists() or not ruta_meta.exists():
        return None

    try:
        meta = json.loads(ruta_meta.read_text(encoding="utf-8"))
        if meta.get("firma") != _firma_archivo(ruta_pdf):
            return None
        if meta.get("version") != VERSION_EXTRACCION:
            return None
        datos = pd.read_csv(ruta_filas, dtype=str, keep_default_na=False)
    except Exception:
        return None

    return ResultadoExtraccion(datos=datos, incidencias=meta.get("incidencias", []))


def _guardar_cache(
    ruta_pdf: Path,
    resultado: ResultadoExtraccion,
    dir_cache: Path,
) -> None:
    """Guarda la extracción de un PDF para no repetirla en la próxima corrida."""
    dir_cache.mkdir(parents=True, exist_ok=True)
    ruta_filas, ruta_meta = _rutas_cache(ruta_pdf, dir_cache)
    try:
        a_texto_csv(resultado.datos).to_csv(ruta_filas, index=False, encoding="utf-8")
        ruta_meta.write_text(
            json.dumps(
                {
                    "firma": _firma_archivo(ruta_pdf),
                    "version": VERSION_EXTRACCION,
                    "incidencias": resultado.incidencias,
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
    except Exception:
        log.warning("No se pudo guardar el caché de %s", ruta_pdf.name)
    
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

def extraer_lote(
    rutas: list[Path],
    cantidades_en_cero: bool = False,
    usar_cache: bool = True,
) -> ResultadoExtraccion:
    """Procesa varios PDF y concatena sus resultados.

    Reutiliza la extracción cacheada de los PDF que no han cambiado, para que
    agregar un archivo nuevo no obligue a releer los anteriores. Las reglas
    posteriores (deduplicación, correcciones, correlativos) se aplican siempre
    sobre el conjunto completo, porque dependen de todos los documentos.
    """
    marcos: list[pd.DataFrame] = []
    incidencias: list[str] = []

    for ruta in rutas:
        cacheado = _leer_cache(ruta, DIR_CACHE) if usar_cache else None
        if cacheado is not None:
            log.info("%s: sin cambios, se reutiliza la extracción anterior", ruta.name)
            resultado = cacheado
        else:
            resultado = extraer_pdf(ruta, cantidades_en_cero)
            if usar_cache:
                _guardar_cache(ruta, resultado, DIR_CACHE)

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

def aplicar_correcciones(
    datos: pd.DataFrame,
    ruta_correcciones: Path,
) -> tuple[pd.DataFrame, list[str]]:
    """Aplica las correcciones manuales autorizadas por el área técnica.

    Existe porque algunos formatos traen errores que no se pueden resolver
    leyendo el PDF: números de solicitud equivocados en el origen, o filas
    que pdfplumber colapsa sin forma segura de separarlas. Corregirlas en el
    código las escondería; en este archivo quedan con su motivo, quién las
    autorizó y cuándo.

    Dos acciones: 'agregar' crea una fila nueva tomando el contexto de la
    página, y 'corregir' cambia el valor de una columna en esa página.
    """
    if not ruta_correcciones.exists():
        return datos, []

    correcciones = pd.read_csv(ruta_correcciones, dtype=str, keep_default_na=False)
    if correcciones.empty:
        return datos, []

    trabajo = datos.copy()
    trabajo["_archivo"] = trabajo["Fuente"].map(_archivo_de_fuente)
    trabajo["_pagina"] = trabajo["Pagina"].astype(str)

    incidencias: list[str] = []
    nuevas: list[dict[str, object]] = []

    for _, c in correcciones.iterrows():
        archivo, pagina = c["archivo"], str(c["pagina"])
        en_pagina = (trabajo["_archivo"] == archivo) & (trabajo["_pagina"] == pagina)

        if not en_pagina.any():
            incidencias.append(
                f"{archivo} pág {pagina}: corrección sin filas que coincidan, se ignora"
            )
            continue

        modelo = trabajo[en_pagina].iloc[0]

        if c["accion"] == "corregir":
            trabajo.loc[en_pagina, c["campo"]] = c["valor"]
            incidencias.append(
                f"{archivo} pág {pagina}: corregido {c['campo']} a {c['valor']!r} "
                f"({c['motivo']}, autorizó {c['autorizado_por']})"
            )

        elif c["accion"] == "agregar":
            fila = {col: modelo[col] for col in COLUMNAS_SALIDA}
            fila["codigo UCAP"] = c["codigo_ucap"]
            fila["Descripcion UCAP"] = c["descripcion"]
            fila["Colocar"] = c["colocar"]
            fila["Quitar"] = c["quitar"]
            fila["Descripcion Normalizada"] = normalizar_descripcion(c["descripcion"])
            fila["Clave Consolidacion"] = c["codigo_ucap"]
            nuevas.append(fila)
            incidencias.append(
                f"{archivo} pág {pagina}: agregado {c['codigo_ucap']} "
                f"({c['motivo']}, autorizó {c['autorizado_por']})"
            )

    trabajo = trabajo.drop(columns=["_archivo", "_pagina"])
    if nuevas:
        trabajo = pd.concat([trabajo, pd.DataFrame(nuevas)], ignore_index=True)

    return trabajo, incidencias

def asignar_identificador_sin_codigo(datos: pd.DataFrame) -> pd.DataFrame:
    """Asigna un identificador correlativo a los ítems que no traen código UCAP.

    Regla del área técnica: los ítems sin código de un mismo documento se
    agrupan bajo un mismo proyecto correlativo (PROY-1, PROY-2...), y dentro
    de cada uno se numera cada ítem distinto (PROY-1-1, PROY-1-2...), para que
    dos materiales distintos del mismo documento no queden indistinguibles.

    El correlativo se asigna ordenando por archivo y número de documento, de
    modo que se mantenga estable entre corridas mientras no cambien los PDF.
    """
    if datos.empty:
        return datos

    salida = datos.copy()
    sin_codigo = salida["codigo UCAP"].fillna("").astype(str).str.strip() == ""
    if not sin_codigo.any():
        return salida

    trabajo = salida[sin_codigo].copy()
    trabajo["_archivo"] = trabajo["Fuente"].map(_archivo_de_fuente)

    documentos = (
        trabajo[["_archivo", "SS/SN"]]
        .drop_duplicates()
        .sort_values(["_archivo", "SS/SN"])
        .reset_index(drop=True)
    )
    numero_doc = {
        (fila["_archivo"], fila["SS/SN"]): i + 1
        for i, fila in documentos.iterrows()
    }

    claves: dict[int, str] = {}
    vistos: dict[int, dict[str, int]] = {}

    for indice, fila in trabajo.iterrows():
        doc = numero_doc[(fila["_archivo"], fila["SS/SN"])]
        item = fila["Descripcion Normalizada"]
        items_doc = vistos.setdefault(doc, {})
        if item not in items_doc:
            items_doc[item] = len(items_doc) + 1
        claves[indice] = f"PROY-{doc}-{items_doc[item]}|{item}"

        salida.loc[list(claves), "Clave Consolidacion"] = list(claves.values())
        salida.loc[list(claves), "codigo UCAP"] = [
        c.split("|")[0] for c in claves.values()
    ]
    return salida


def ejecutar(
    rutas: list[Path],
    ruta_salida: Path,
    modo_append: bool = False,
    cantidades_en_cero: bool = False,
    usar_cache: bool = True,
) -> ResultadoExtraccion:
    """Punto de entrada del pipeline completo."""
    resultado = extraer_lote(rutas, cantidades_en_cero,usar_cache)

    depurados, descartes = resolver_paginas_duplicadas(resultado.datos)
    depurados, correcciones = aplicar_correcciones(depurados, RUTA_CORRECCIONES)
    depurados = asignar_identificador_sin_codigo(depurados)
    incidencias = resultado.incidencias + descartes + correcciones

    datos = (
        fusionar_con_historico(depurados, ruta_salida)
        if modo_append
        else a_texto_csv(depurados)
    )

    escribir_csv(datos, ruta_salida)
    return ResultadoExtraccion(datos=datos, incidencias=incidencias)