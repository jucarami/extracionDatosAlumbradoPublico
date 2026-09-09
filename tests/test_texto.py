import pytest

from ucap_etl.texto import (
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
        ("UCAP TRIPLEX AL 2X4+1X4 XLP,AEREO", "UCAP TRIPLEX AL 2X4+1X4 XLP AEREO"),
        ('PROYEC LED 168W TIPO V MEDIA (MEDIUM "M") 5000K',
         "PROYEC LED 168W TIPO V MEDIA MEDIUM M 5000K"),
        ("UCAP PROY. 1000W.", "UCAP PROY 1000W"),
        ("Cruceta 3600 mm", "CRUCETA 3600 MM"),
        ("", ""),
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