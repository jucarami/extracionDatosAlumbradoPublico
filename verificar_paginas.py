import sys
sys.path.insert(0, "src")

from collections import Counter

import pdfplumber

from ucap_etl.modelos import ContextoPagina
from ucap_etl.paginas import procesar_pagina

RUTAS = [
    "data/raw/Tablas 1 al 392_2025.pdf",
    "data/raw/Tabla 1 al 331_2026.pdf",
]

for ruta in RUTAS:
    nombre = ruta.split("/")[-1]
    total_registros = 0
    incidencias = []
    movimientos = Counter()
    sin_codigo = 0
    contexto = ContextoPagina()

    with pdfplumber.open(ruta) as pdf:
        for n, pagina in enumerate(pdf.pages, start=1):
            r = procesar_pagina(pagina, n, nombre, contexto)
            contexto = r.contexto
            total_registros += len(r.registros)
            incidencias.extend(r.incidencias)
            for reg in r.registros:
                movimientos[reg.movimiento] += 1
                if not reg.codigo:
                    sin_codigo += 1

    print(f"\n===== {nombre} =====")
    print(f"Registros extraídos: {total_registros}")
    print(f"Sin código UCAP:     {sin_codigo}")
    print(f"Movimientos:         {dict(movimientos)}")
    print(f"Incidencias:         {len(incidencias)}")
    for linea in incidencias[:30]:
        print("   ", linea)