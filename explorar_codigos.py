import re
from collections import Counter

import pdfplumber

RUTAS = [
    "data/raw/Tablas 1 al 392_2025.pdf",
    "data/raw/Tabla 1 al 331_ 2026.pdf",
]

for ruta in RUTAS:
    patrones = Counter()
    ejemplos = {}
    with pdfplumber.open(ruta) as pdf:
        for pagina in pdf.pages:
            for tabla in pagina.extract_tables() or []:
                for fila in tabla:
                    celda = (fila[0] or "").replace("\n", " ").strip()
                    if not celda:
                        continue
                    forma = re.sub(r"\d", "9", re.sub(r"[A-Za-zÁÉÍÓÚÑ]", "A", celda))
                    patrones[forma] += 1
                    ejemplos.setdefault(forma, celda)

    print(f"\n===== {ruta} =====")
    for forma, cuenta in patrones.most_common(30):
        print(f"{cuenta:6}  {forma:20}  ej: {ejemplos[forma]!r}")