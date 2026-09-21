import pandas as pd

from ucap_etl.pipeline import resolver_paginas_duplicadas


def _fila(pagina, documento, colocar, archivo="val_2026.pdf", proyecto="OBRA A"):
    """Fábrica de filas mínimas: solo las columnas que usa la deduplicación."""
    return {
        "Pagina": pagina,
        "SS/SN": documento,
        "Proyecto": proyecto,
        "Colocar": colocar,
        "Fuente": f"{archivo}, pagina {pagina}",
    }


def test_mismo_ss_conserva_la_de_mayor_colocar():
    datos = pd.DataFrame([
        _fila(112, "1349121", 50),
        _fila(112, "1349121", 58),
        _fila(113, "1349121", 20),
    ])
    resultado, incidencias = resolver_paginas_duplicadas(datos)
    assert set(resultado["Pagina"]) == {112}
    assert len(incidencias) == 1


def test_ss_distintos_se_conservan_todos():
    datos = pd.DataFrame([
        _fila(132, "1359705", 10),
        _fila(134, "1359721", 10),
    ])
    resultado, incidencias = resolver_paginas_duplicadas(datos)
    assert len(resultado) == 2
    assert incidencias == []


def test_empate_gana_la_pagina_menor():
    datos = pd.DataFrame([
        _fila(211, "1371806", 1),
        _fila(212, "1371806", 1),
    ])
    resultado, _ = resolver_paginas_duplicadas(datos)
    assert set(resultado["Pagina"]) == {211}


def test_mismo_ss_en_archivos_distintos_se_conserva():
    """Cada PDF se evalúa solo contra sí mismo."""
    datos = pd.DataFrame([
        _fila(220, "1119690", 27, archivo="Tablas_2025.pdf"),
        _fila(174, "1119690", 9, archivo="val_2026.pdf"),
    ])
    resultado, _ = resolver_paginas_duplicadas(datos)
    assert len(resultado) == 2


def test_filas_sin_numero_no_se_deduplican():
    datos = pd.DataFrame([
        _fila(98, "", 36),
        _fila(99, "", 5),
    ])
    resultado, _ = resolver_paginas_duplicadas(datos)
    assert len(resultado) == 2


def test_mismo_ss_con_proyectos_distintos_se_conserva_y_reporta():
    """Caso real: SS 1159547 en 2025, págs 97 y 118, dos obras distintas."""
    datos = pd.DataFrame([
        _fila(97, "1159547", 19, proyecto="SMAP-0221-25 CR 34 CL 10A"),
        _fila(118, "1159547", 2, proyecto="Sendero Las independencias"),
    ])
    resultado, incidencias = resolver_paginas_duplicadas(datos)
    assert len(resultado) == 2
    assert any("digitación" in i for i in incidencias)


def test_proyecto_igual_con_distinta_escritura_si_duplica():
    """Tildes, mayúsculas y comas no cambian la identidad del proyecto."""
    datos = pd.DataFrame([
        _fila(154, "1348589", 16, proyecto="Vía CR 81 CL 54"),
        _fila(195, "1348589", 14, proyecto="VIA CR 81, CL 54"),
    ])
    resultado, _ = resolver_paginas_duplicadas(datos)
    assert set(resultado["Pagina"]) == {154}


def test_datos_vacios_no_fallan():
    datos = pd.DataFrame(columns=["Pagina", "SS/SN", "Proyecto", "Colocar", "Fuente"])
    resultado, incidencias = resolver_paginas_duplicadas(datos)
    assert resultado.empty
    assert incidencias == []