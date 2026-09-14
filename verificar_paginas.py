import sys
sys.path.insert(0, "src")

import pdfplumber

RUTA = "data/raw/Tabla 1 al 331_2026.pdf"


# ============================================================
# PARTE 1: dónde cae cada palabra de la página 40
# ============================================================
print("=" * 60)
print("PARTE 1: palabras de la página 40 con su posición")
print("=" * 60)

with pdfplumber.open(RUTA) as pdf:
    p = pdf.pages[39]
    for w in p.extract_words():
        print(f"top={w['top']:7.1f}  x0={w['x0']:7.1f}  {w['text']!r}")


# ============================================================
# PARTE 2: las coordenadas de columna son iguales en todas?
# ============================================================
print()
print("=" * 60)
print("PARTE 2: líneas verticales por página")
print("=" * 60)

with pdfplumber.open(RUTA) as pdf:
    for n in (1, 40, 50, 150, 300):
        p = pdf.pages[n - 1]
        xs = sorted(
            {round(l["x0"]) for l in p.lines} | {round(l["x1"]) for l in p.lines}
        )
        print(f"pág {n:4}  verticales: {xs}")