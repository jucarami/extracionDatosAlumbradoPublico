import pytest

from ucap_etl.texto import (
    es_codigo_ucap,
    limpiar_celda,
    normalizar_descripcion,
    parsear_cantidad,
    quitar_tildes,
)


# --------------------------------------------------- limpiar_celda

@pytest.mark.parametrize(
    "entrada,esperado",
    [
        ("UCAP  POSTE\nPRFV 18M ", "UCAP POSTE PRFV 18M"),
        (None, ""),
        ("   ", ""),
        ("133", "133"),
    ],
)
def test_limpiar_celda(entrada, esperado):
    assert limpiar_celda(entrada) == esperado


# --------------------------------------------------- quitar_tildes

def test_quitar_tildes():
    assert quitar_tildes("DESCRIPCIÓN UCAP") == "DESCRIPCION UCAP"


# --------------------------------------------------- normalizar_descripcion

@pytest.mark.parametrize(
    "entrada,esperado",
    [
        ("UCAP TRIPLEX AL 2X4+1X4 XLP,AEREO", "TRIPLEX AL 2X4+1X4 XLP AEREO"),
        ('PROYEC LED 168W TIPO V MEDIA (MEDIUM "M") 5000K',
         "PROYEC LED 168W TIPO V MEDIA MEDIUM M 5000K"),
        ("UCAP PROY. 1000W.", "PROY 1000W"),
        ("Cruceta 3600 mm", "CRUCETA 3600 MM"),
        ("", ""),
        ("UCAP POSTE CONCRETO REDONDO 12M", "POSTE CONCRETO REDONDO 12M"),
        ("Ucap Poste Concreto Redondo 12M", "POSTE CONCRETO REDONDO 12M"),
        ("POSTE CONCRETO REDONDO 12M", "POSTE CONCRETO REDONDO 12M"),
    ],
)
def test_normalizar_descripcion(entrada, esperado):
    assert normalizar_descripcion(entrada) == esperado


# --------------------------------------------------- parsear_cantidad

@pytest.mark.parametrize(
    "entrada,esperado",
    [
        ("133", 133),
        ("1.234", 1234),
        ("12,5", 12.5),
        ("  96 ", 96),
        ("abc", None),
    ],
)
def test_parsear_cantidad(entrada, esperado):
    assert parsear_cantidad(entrada) == esperado


def test_cantidad_vacia_no_es_cero():
    assert parsear_cantidad("") is None
    assert parsear_cantidad("", en_cero=True) == 0
    
@pytest.mark.parametrize(
    "entrada,esperado",
    [
        ("5200272", True),
        ("5090209", True),
        ("R5200219", True),
        ("5200238-3", True),
        ("211332", True),
        ("55220000446149", True),
        ("", False),
        ("abc", False),
        ("12", False),
        ("Código UCAP", False),
        ("5200407 ", False),
    ],
)
def test_es_codigo_ucap(entrada, esperado):
    assert es_codigo_ucap(entrada) is esperado