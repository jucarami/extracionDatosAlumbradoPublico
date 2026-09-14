"""Configuración central del ETL: esquema de salida y rutas."""

from __future__ import annotations
from pathlib import Path
import re

# config.py -> ucap_etl -> src -> raíz del proyecto
RAIZ_PROYECTO = Path(__file__).resolve().parents[2]
DIR_RAW = RAIZ_PROYECTO / "data" / "raw"
DIR_PROCESSED = RAIZ_PROYECTO / "data" / "processed"
DIR_LOGS = RAIZ_PROYECTO / "logs"

#: Orden exacto de columnas del CSV histórico. No reordenar sin migrar el CSV.
COLUMNAS_SALIDA: tuple[str, ...] = (
    "Pagina",
    "Tipo",
    "SS/SN",
    "Proyecto",
    "codigo UCAP",
    "Descripcion UCAP",
    "Colocar",
    "Quitar",
    "Descripcion Normalizada",
    "Fuente",
    "Clave Consolidacion",
)

#: Columnas que identifican una fila ya cargada (deduplicación en modo append).
CLAVE_DEDUPLICACION: tuple[str, ...] = (
    "Fuente",
    "Clave Consolidacion",
    "Descripcion UCAP",
    "Colocar",
    "Quitar",
)

#: Etiquetas del encabezado de columnas, ya sin tildes y en mayúsculas.
ETIQUETA_CODIGO = "CODIGO"
ETIQUETA_DESCRIPCION = "DESCRIPCION"
ETIQUETA_COLOCAR = "COLOCAR"
ETIQUETA_QUITAR = "QUITAR"


RE_TIPO_DOCUMENTO = re.compile(r"^(SS|SN)$", re.IGNORECASE)
RE_NUMERO_DOCUMENTO = re.compile(r"^\d{4,10}$")
