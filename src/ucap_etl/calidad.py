"""Control de calidad sobre el resultado del ETL.

No corrige datos: los mide y los reporta. Cualquier corrección automática
escondería la pérdida de información que este módulo existe para revelar.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

log = logging.getLogger(__name__)


def _vacias(serie: pd.Series) -> int:
    return int((serie.astype(str).str.strip() == "").sum())


def calcular_metricas(datos: pd.DataFrame) -> dict[str, int]:
    """Métricas de integridad del histórico extraído."""
    if datos.empty:
        return {"filas": 0}

    return {
        "filas": len(datos),
        "documentos_unicos": int(datos["SS/SN"].nunique()),
        "paginas": int(datos["Fuente"].nunique()),
        "ucaps_distintos": int(datos["Clave Consolidacion"].nunique()),
        "sin_codigo_ucap": _vacias(datos["codigo UCAP"]),
        "sin_proyecto": _vacias(datos["Proyecto"]),
        "sin_numero_documento": _vacias(datos["SS/SN"]),
    }
    
def resumen_por_documento(datos: pd.DataFrame) -> pd.DataFrame:
    """Totales por documento, para conciliar manualmente contra el PDF."""
    if datos.empty:
        return pd.DataFrame()

    numerico = datos.copy()
    for columna in ("Colocar", "Quitar"):
        numerico[columna] = pd.to_numeric(numerico[columna], errors="coerce")

    return (
        numerico.groupby(["Fuente", "Tipo", "SS/SN", "Proyecto"], dropna=False)
        .agg(
            ucaps=("Descripcion UCAP", "count"),
            colocar=("Colocar", "sum"),
            quitar=("Quitar", "sum"),
        )
        .reset_index()
    )
    
def reportar(datos: pd.DataFrame, incidencias: list[str], ruta_log: Path) -> None:
    """Imprime las métricas y vuelca las incidencias a disco."""
    metricas = calcular_metricas(datos)

    log.info("--- Control de calidad ---")
    for nombre, valor in metricas.items():
        log.info("%-24s %s", nombre, valor)

    if metricas.get("sin_codigo_ucap"):
        log.info(
            "Los registros sin código conservan la celda vacía: se cruzan por "
            "Descripcion Normalizada, nunca se colapsan bajo una etiqueta común."
        )

    if incidencias:
        ruta_log.parent.mkdir(parents=True, exist_ok=True)
        ruta_log.write_text("\n".join(incidencias), encoding="utf-8")
        log.warning("Incidencias: %d, ver %s", len(incidencias), ruta_log)
        for linea in incidencias[:15]:
            log.warning("   %s", linea)
            
            