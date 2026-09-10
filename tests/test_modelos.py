import pytest

from ucap_etl.config import COLUMNAS_SALIDA
from ucap_etl.modelos import ContextoPagina, RegistroUCAP


# --------------------------------------------------- ContextoPagina

def test_contexto_vacio_no_esta_completo():
    assert ContextoPagina().esta_completo is False


def test_contexto_completo():
    ctx = ContextoPagina(proyecto="SMAP 299", tipo="SN", numero="193679")
    assert ctx.esta_completo is True
    assert ctx.documento == "193679"


def test_contexto_sin_numero_no_esta_completo():
    assert ContextoPagina(proyecto="SMAP 299", tipo="SN").esta_completo is False


# --------------------------------------------------- RegistroUCAP

def _registro(codigo="5200272", colocar=16, quitar=None,
              descripcion="LUM LED (SEPIALED II) 128W"):
    """Fábrica de registros para las pruebas: cambia solo lo que importa."""
    return RegistroUCAP(
        pagina=1,
        contexto=ContextoPagina(proyecto="SMAP 299", tipo="SN", numero="193679"),
        codigo=codigo,
        descripcion=descripcion,
        colocar=colocar,
        quitar=quitar,
        fuente="Tablas 1 al 392_2025.pdf, pagina 1",
    )


@pytest.mark.parametrize(
    "colocar,quitar,esperado",
    [
        (16, None, "COLOCAR"),
        (None, 16, "QUITAR"),
        (5, 5, "AMBOS"),
        (None, None, "NULO"),
        (0, 0, "NULO"),
    ],
)
def test_movimiento(colocar, quitar, esperado):
    assert _registro(colocar=colocar, quitar=quitar).movimiento == esperado


def test_descripcion_normalizada():
    r = _registro(descripcion="UCAP POSTE CONCRETO REDONDO 12M")
    assert r.descripcion_normalizada == "POSTE CONCRETO REDONDO 12M"


def test_clave_es_el_codigo_crudo():
    assert _registro().clave_consolidacion() == "5200272"


def test_clave_conserva_prefijo_de_retiro():
    r = _registro(codigo="R5200219", colocar=None, quitar=16)
    assert r.clave_consolidacion() == "R5200219"


def test_clave_conserva_sufijo_con_guion():
    assert _registro(codigo="5200238-3").clave_consolidacion() == "5200238-3"


def test_clave_sin_codigo_lleva_marcador_y_descripcion():
    r = _registro(codigo="", descripcion="Cruceta 3600 mm")
    assert r.clave_consolidacion() == "SIN CODIGO|CRUCETA 3600 MM"


def test_items_sin_codigo_distintos_no_colapsan():
    """Crucetas y punta captadora son físicamente distintas."""
    a = _registro(codigo="", descripcion="Cruceta 3600 mm")
    b = _registro(codigo="", descripcion="Cruceta 1500 mm")
    c = _registro(codigo="", descripcion="Punta captadora Franklin")
    claves = {a.clave_consolidacion(), b.clave_consolidacion(), c.clave_consolidacion()}
    assert len(claves) == 3


def test_prefijo_ucap_no_parte_el_mismo_item():
    """'UCAP POSTE...' y 'POSTE...' son el mismo ítem sin código."""
    con = _registro(codigo="", descripcion="UCAP POSTE CONCRETO REDONDO 12M")
    sin = _registro(codigo="", descripcion="POSTE CONCRETO REDONDO 12M")
    assert con.clave_consolidacion() == sin.clave_consolidacion()


# --------------------------------------------------- a_dict

def test_a_dict_respeta_el_esquema():
    assert tuple(_registro().a_dict().keys()) == COLUMNAS_SALIDA


def test_a_dict_aplana_el_contexto():
    d = _registro().a_dict()
    assert d["Tipo"] == "SN"
    assert d["SS/SN"] == "193679"
    assert d["Proyecto"] == "SMAP 299"


def test_a_dict_conserva_descripcion_cruda():
    """La columna cruda mantiene el prefijo; solo la normalizada lo pierde."""
    d = _registro(descripcion="UCAP POSTE CONCRETO REDONDO 12M").a_dict()
    assert d["Descripcion UCAP"] == "UCAP POSTE CONCRETO REDONDO 12M"
    assert d["Descripcion Normalizada"] == "POSTE CONCRETO REDONDO 12M"