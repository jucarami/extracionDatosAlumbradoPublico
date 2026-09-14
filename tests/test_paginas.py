from ucap_etl.modelos import ContextoPagina
from ucap_etl.paginas import ResultadoPagina, _es_fila_de_relleno, _leer


# --------------------------------------------------- _leer

def test_leer_por_nombre_logico():
    fila = ["5200272", "LUM LED", "16", ""]
    mapa = {"codigo": 0, "descripcion": 1, "colocar": 2, "quitar": 3}
    assert _leer(fila, mapa, "codigo") == "5200272"
    assert _leer(fila, mapa, "quitar") == ""


def test_leer_tolera_filas_cortas():
    """extract_tables a veces devuelve filas con menos celdas."""
    fila = ["5200272", "LUM LED"]
    mapa = {"codigo": 0, "descripcion": 1, "colocar": 2, "quitar": 3}
    assert _leer(fila, mapa, "colocar") == ""


# --------------------------------------------------- _es_fila_de_relleno

def test_fila_vacia_es_relleno():
    assert _es_fila_de_relleno("", "", None, None) is True


def test_fila_con_cantidad_no_es_relleno():
    """Si hay cantidad, algo se perdió: no se descarta en silencio."""
    assert _es_fila_de_relleno("", "", None, 18) is False


def test_fila_con_descripcion_no_es_relleno():
    assert _es_fila_de_relleno("", "Cruceta 3600 mm", None, None) is False


def test_ceros_cuentan_como_sin_cantidad():
    assert _es_fila_de_relleno("", "", 0, 0) is True


# --------------------------------------------------- ResultadoPagina

def test_resultado_arranca_vacio():
    r = ResultadoPagina()
    assert r.registros == []
    assert r.incidencias == []
    assert r.contexto == ContextoPagina()


def test_resultados_no_comparten_listas():
    """field(default_factory=list) evita que dos páginas compartan estado."""
    a = ResultadoPagina()
    b = ResultadoPagina()
    a.registros.append("x")
    assert b.registros == []