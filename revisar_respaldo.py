import sys
sys.path.insert(0, "src")

import pdfplumber

from ucap_etl.extraccion import detectar_tabla, localizar_encabezado

RUTAS = [
    "data/raw/Tablas 1 al 392_2025.pdf",
    "data/raw/Tabla 1 al 331_2026.pdf",
    "data/raw/UCAP EN VALIDACION DE APROBACION_2026.pdf",
]

total = 0
for ruta in RUTAS:
    with pdfplumber.open(ruta) as pdf:
        for n, pagina in enumerate(pdf.pages, start=1):
            tabla = detectar_tabla(pagina)
            if tabla is None:
                continue
            indice, _ = localizar_encabezado(tabla)
            if indice is None:
                continue
            for fila in tabla[indice + 1:]:
                if len(fila) < 4:
                    continue
                codigo = fila[0].strip()
                if codigo and " " in codigo:
                    total += 1
                    print(f"\n{ruta[9:]} pág {n}")
                    print(f"  codigo:      {codigo!r}")
                    print(f"  descripcion: {fila[1]!r}")
                    print(f"  colocar:     {fila[2]!r}")
                    print(f"  quitar:      {fila[3]!r}")

print(f"\n=== Total de filas colapsadas: {total} ===")