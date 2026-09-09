from __future__ import annotations

import re
import unicodedata

_ESPACIOS = re.compile(r"\s+")
_PUNTUACION_RUIDO = re.compile(r"[,;:()\[\]]")
_PUNTO_FINAL = re.compile(r"\s*\.\s*$")
_PUNTO_ABREVIATURA = re.compile(r"(?<=[A-Z])\.(?=\s|$)")


def limpiar_celda(valor: object) -> str:
    """Normaliza una celda cruda de pdfplumber a un str sin ruido."""
    if valor is None:
        return ""
    texto = str(valor).replace("\n", " ").replace("\xa0", " ")
    return _ESPACIOS.sub(" ", texto).strip()


def quitar_tildes(texto: str) -> str:
    """Elimina diacríticos preservando la letra base."""
    return "".join(
        c for c in unicodedata.normalize("NFD", texto)
        if unicodedata.category(c) != "Mn"
    )


def normalizar_descripcion(texto: str) -> str:
    """Descripción canónica para cruzar contra el catálogo UCAP."""
    if not texto:
        return ""
    t = quitar_tildes(texto).upper()
    t = t.replace('"', " ").replace("'", " ")
    t = _PUNTUACION_RUIDO.sub(" ", t)
    t = _PUNTO_FINAL.sub("", t)
    t = _PUNTO_ABREVIATURA.sub(" ", t)
    return _ESPACIOS.sub(" ", t).strip()


def parsear_cantidad(valor: object, en_cero: bool = False) -> int | float | None:
    """Convierte una cantidad del formato a número.

    Formato colombiano: punto = miles, coma = decimal.
    Celda vacía -> None (o 0 si en_cero), porque vacío significa
    "el movimiento no aplica", no "cantidad cero".
    """
    texto = limpiar_celda(valor)
    if not texto:
        return 0 if en_cero else None

    texto = texto.replace(" ", "")
    if "," in texto:
        texto = texto.replace(".", "").replace(",", ".")
    else:
        texto = texto.replace(".", "")

    try:
        numero = float(texto)
    except ValueError:
        return None
    return int(numero) if numero.is_integer() else numero


def construir_fuente(nombre_archivo: str, pagina: int) -> str:
    """Trazabilidad al documento origen."""
    return f"{nombre_archivo}, pagina {pagina}"

