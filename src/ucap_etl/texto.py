from __future__ import annotations

import re
import unicodedata

_ESPACIOS = re.compile(r"\s+")
_PUNTUACION_RUIDO = re.compile(r"[,;:()\[\]]")
_PUNTO_FINAL = re.compile(r"\s*\.\s*$")
_PUNTO_ABREVIATURA = re.compile(r"(?<=[A-Z])\.(?=\s|$)")
_CODIGO_UCAP = re.compile(r"^[A-Z]?\d{5,14}(-\d+)?$")
_PREFIJO_UCAP = re.compile(r"^UCAP\b\s*")


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

def es_codigo_ucap(valor: str) -> bool:
    """True si el valor tiene forma de código UCAP.

    Formas verificadas contra los 723 folios de 2025 y 2026:
      - 5 a 14 dígitos: '5200272', '211332', '55220000446149'
      - prefijo opcional de una letra: 'R5200219' (R marca retiro)
      - sufijo opcional con guión: '5200238-3' (variantes distintas entre sí)

    Todos los casos de 6 y 14 dígitos se inspeccionaron uno por uno: traen
    descripción y cantidad válidas, así que se aceptan.

    El código se conserva crudo, con prefijo y sufijo: es lo que dice el
    documento y la transformación es reversible, la fusión no.

    Asume que el valor ya viene limpio de limpiar_celda().
    """
    return bool(_CODIGO_UCAP.match(valor))

def normalizar_descripcion(texto: str) -> str:
    """Descripción canónica para cruzar contra el catálogo UCAP.

    Quita el prefijo 'UCAP' inicial: se verificó contra los 723 folios que
    30 de las 67 descripciones con prefijo existen también sin él para el
    mismo ítem. Es inconsistencia de captura, no información.
    """
    if not texto:
        return ""
    t = quitar_tildes(texto).upper()
    t = _PREFIJO_UCAP.sub("", t)
    t = t.replace('"', " ").replace("'", " ")
    t = _PUNTUACION_RUIDO.sub(" ", t)
    t = _PUNTO_FINAL.sub("", t)
    t = _PUNTO_ABREVIATURA.sub(" ", t)
    return _ESPACIOS.sub(" ", t).strip()

