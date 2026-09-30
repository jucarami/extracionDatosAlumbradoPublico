# Extracción de formatos UCAP AP

Proyecto de extracción de los formatos UCAP AP (EPM, Unidad Alumbrado) desde PDF hacia un CSV histórico que sirve como fuente de datos para el estudio tarifario (ETR) de alumbrado público de Medellín.

Cada página de los PDF contiene un formato con el mismo diseño: un encabezado con el proyecto y su número de solicitud, y una tabla de detalle con los códigos UCAP que se colocan o se quitan. El objetivo es convertir esas páginas en filas, una por código UCAP, con el contexto de la hoja replicado en cada una.

## Estado actual

Terminado, validado y empaquetado como ejecutable para uso del área técnica.

| PDF | Páginas | Contenido |
|---|---|---|
| `Tablas 1 al 392_2025.pdf` | 392 | Formatos de 2025 |
| `Tabla 1 al 331_2026.pdf` | 331 | Formatos de 2026 |
| `UCAP EN VALIDACION DE APROBACION_2026.pdf` | 245 | Formatos en validación de aprobación, 2026 |

| Módulo | Qué hace |
|---|---|
| `texto.py` | Limpieza y normalización de celdas, cantidades, códigos y año |
| `config.py` | Esquema de columnas, rutas, patrones y versión de extracción |
| `modelos.py` | Representación de un registro y su clave de consolidación |
| `extraccion.py` | Detección de tabla, mapeo de columnas y lectura del encabezado |
| `paginas.py` | Reglas de negocio por página, herencia de encabezado e incidencias |
| `pipeline.py` | Caché, recorrido de los PDF, deduplicación, correcciones y escritura |
| `calidad.py` | Métricas y reporte de anomalías |
| `cli.py` | Interfaz de línea de comandos |
| `lanzador.py` | Punto de entrada del ejecutable, para uso sin terminal |

Cifras de la última corrida:

| Métrica | Valor |
|---|---|
| Registros | 4109 |
| Páginas conservadas | 937 de 968 |
| Documentos únicos | 923 |
| UCAP distintos | 177 |
| Páginas descartadas por duplicado | 30 |
| Incidencias reportadas | 92 |
| Pruebas automatizadas | 77 |

## Estructura

```
alumbradoPublico/
├── main.py                punto de entrada para línea de comandos
├── lanzador.py            punto de entrada del ejecutable
├── src/ucap_etl/          código del paquete
├── tests/                 pruebas automatizadas
├── data/raw/              PDF de entrada (no se versionan)
├── data/cache/            extracciones cacheadas (no se versionan)
├── data/correcciones.csv  correcciones manuales autorizadas (sí se versiona)
├── data/processed/        CSV de salida
├── logs/                  reportes de incidencias
└── pyproject.toml         configuración del proyecto
```

Los módulos se organizan de adentro hacia afuera, y ninguno importa a otro que esté a su derecha:

```
texto  →  modelos  →  extraccion  →  paginas  →  pipeline  →  cli
```

Gracias a esa separación, `texto.py` y `modelos.py` no conocen pdfplumber ni pandas, y por eso las 77 pruebas corren en menos de un segundo.

## Librerías

Cuatro externas: `pdfplumber` para leer los PDF, `pandas` para los datos tabulares, `pytest` para las pruebas y `pyinstaller` para empaquetar. Las dos últimas son solo de desarrollo.

Del resto se encarga la biblioteca estándar: `re`, `unicodedata`, `pathlib`, `dataclasses`, `logging`, `argparse`, `csv`, `json`, `glob` y `sys`.

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install pdfplumber pandas pytest pyinstaller
```

## Uso desde la línea de comandos

```powershell
# Procesar todos los PDF de data/raw
python main.py "data/raw/*.pdf" -o data/processed/ucap_historico.csv

# Inspeccionar una página antes de procesar el lote completo
python main.py "data/raw/Tabla 1 al 331_2026.pdf" --debug 40

# Reprocesar todo ignorando el caché
python main.py "data/raw/*.pdf" --sin-cache

# Totales por documento, para conciliar contra el PDF
python main.py "data/raw/*.pdf" --resumen

# Verificar que nada se rompió
pytest -v
```

| Opción | Efecto |
|---|---|
| `-o`, `--out` | Ruta del CSV de salida |
| `--append` | Agrega al histórico existente y deduplica |
| `--ceros` | Escribe 0 en Colocar y Quitar vacíos |
| `--sin-cache` | Reprocesa todos los PDF ignorando el caché |
| `--debug N` | Vuelca la tabla cruda y el contexto de la página N |
| `--resumen` | Imprime los totales por documento |
| `-v` | Salida detallada |

## Uso del ejecutable

Para el área técnica existe `ProcesarUCAP.exe`, que no requiere instalar Python. Se entrega en una carpeta con esta estructura:

```
ProcesarUCAP.exe
data\correcciones.csv
PDF_entrada\          (vacía, ahí se copian los PDF)
```

Las carpetas `CSV_salida`, `logs` y `data\cache` las crea el propio programa.

Instructivo para el usuario:

1. Guardar en `PDF_entrada` los PDF que lleguen. El nombre debe incluir el año.
2. Doble clic en `ProcesarUCAP.exe`.
3. El resultado queda en `CSV_salida\ucap_historico.csv`.
4. Revisar `logs\ucap_historico.incidencias.log` si algo no cuadra.
5. **No borrar los PDF anteriores de la carpeta.** El proceso los necesita todos.
6. La primera vez Windows pedirá confirmar, porque el ejecutable no está firmado: *Más información* y luego *Ejecutar de todas formas*.

El punto 5 es el más importante. El histórico se regenera completo en cada corrida; si se borran los PDF viejos, el CSV se queda solo con el último.

Para regenerar el ejecutable después de cambiar el código:

```powershell
pyinstaller --onefile --name ProcesarUCAP --paths src --collect-data pdfminer --collect-all pypdfium2 lanzador.py
```

## Esquema de salida

| Columna | Origen |
|---|---|
| `Anio` | Año tomado del nombre del PDF |
| `Pagina` | Número de página dentro del PDF |
| `Tipo` | Literal SS o SN del encabezado |
| `SS/SN` | Número de solicitud que aparece a la derecha del literal |
| `Proyecto` | Texto que sigue a la etiqueta "Proyecto:" |
| `codigo UCAP` | Primera columna del detalle, o el identificador asignado si no trae código |
| `Descripcion UCAP` | Segunda columna, texto crudo tal como aparece en el documento |
| `Colocar` | Tercera columna, convertida a número |
| `Quitar` | Cuarta columna, convertida a número |
| `Descripcion Normalizada` | Descripción canónica para cruzar contra el catálogo |
| `Fuente` | Nombre del archivo y página de origen |
| `Clave Consolidacion` | Llave hacia el catálogo de UCAP |

## Decisiones tomadas

Cada decisión de este apartado se tomó midiendo primero sobre los folios reales, nunca por suposición.

### El código UCAP se conserva tal como viene

En los documentos aparecen varias formas: numéricos de siete dígitos como `5200272`, con prefijo de letra como `R5200219` donde la R marca retiro, con sufijo como `5200238-3` o `5200207-1`, de seis dígitos como `211332`, y de catorce dígitos como `55220000446149`.

Todos se guardan crudos. Quitar el prefijo o el sufijo sería irreversible: si dos códigos que parecían iguales resultan ser ítems distintos, ya no hay manera de separarlos.

### Los ítems sin código reciben un identificador correlativo

Algunos ítems del formato no traen código UCAP: crucetas, punta captadora, tuberías, cajas de paso. Son 32 registros repartidos en 14 documentos.

Por regla del área técnica, los ítems sin código de un mismo documento se agrupan bajo un proyecto correlativo (`PROY-1`, `PROY-2`) y dentro de cada uno se numera cada ítem distinto: `PROY-1-1`, `PROY-1-2`, `PROY-1-3`. Sin ese segundo número, cinco materiales distintos del mismo documento quedarían indistinguibles al agrupar.

El correlativo se asigna ordenando por archivo y número de documento, no por orden de aparición, para que se mantenga estable entre corridas mientras no cambien los PDF.

La `Clave Consolidacion` de esas filas lleva además la descripción normalizada, por ejemplo `PROY-7-1|CRUCETA 3600 MM`.

### El prefijo UCAP se retira de la descripción normalizada

De las 67 descripciones que empiezan por la palabra UCAP, 30 existen también escritas sin ese prefijo para el mismo ítem. Es inconsistencia de digitación, no información, y si no se unifica esos ítems quedan partidos en dos al agrupar.

La columna `Descripcion UCAP` conserva el texto crudo con prefijo. Solo la normalizada lo pierde.

### Una celda vacía no es un cero

Cuando la columna Colocar viene vacía significa que ese UCAP no se coloca, se quita. Escribir cero produciría valores falsos al promediar o contar en el tablero.

Las cantidades se escriben al CSV como texto formateado, porque pandas promueve la columna a decimal al mezclar enteros con nulos y escribiría `4.0` donde el formato dice `4`.

### El número de solicitud no entra en la clave

El número es único en el universo de documentos, así que el prefijo SS o SN no aporta a la llave. El tipo se conserva en su propia columna para trazabilidad.

### Las anotaciones no entran al histórico

Notas escritas a mano en la columna de descripción, subtítulos de sección y comentarios del técnico no tienen código ni cantidad, así que se descartan. Cada una queda en el log con su página.

### Un reemplazo es una sola fila

Cerca del ocho por ciento de los registros trae cantidad en Colocar y en Quitar a la vez. Son reemplazos: se retiran unidades viejas y se colocan nuevas del mismo ítem. Se guardan tal como vienen, y la propiedad `movimiento` los clasifica como AMBOS.

### El año viene del nombre del archivo

Es una convención de nombrado, no un dato del formato. Si el archivo no lo trae, el ejecutable se niega a procesar y dice cuál renombrar, en vez de generar un CSV con la columna vacía.

### Una página hereda encabezado solo si no trae nada propio

Si una hoja no trae ni proyecto ni número de solicitud, se considera continuación de la anterior. Si trae cualquiera de los dos, es un documento distinto: sus datos faltantes se reportan y nunca se rellenan con los de otra hoja.

Esta regla falló dos veces en direcciones opuestas antes de quedar así. En las hojas de telegestión el nombre no se leía completo pero el número era propio, y heredaban un número ajeno. En la página 98 de 2026 el número venía en cero pero el proyecto era propio, y heredaba el proyecto anterior. Ambos casos tienen prueba automatizada.

### Deduplicación de páginas repetidas

Si dentro de un mismo PDF un documento aparece en varias páginas con el mismo número y el mismo proyecto, es duplicación del formato: se conserva la página con mayor suma en Colocar, y en empate gana la de menor número de página.

Tres límites:

1. **Cada PDF se evalúa solo contra sí mismo.** Un documento que aparece en 2025 y en validación 2026 se conserva en ambos, porque puede ser el mismo trabajo en dos estados.
2. **Si el número se repite con proyectos distintos, no es duplicado.** Es un probable error de digitación: se conservan todas las páginas y se reporta.
3. **Los números distintos se conservan aunque compartan estructura.** Es común que un formato se copie del diseño del proyecto anterior.

El nombre del proyecto se compara sin tildes, mayúsculas ni comas. De las 30 páginas descartadas, 25 son copias idénticas; las otras cinco tienen el mismo proyecto pero contenido distinto y quedan listadas en el log con el conteo de ítems de ambas páginas.

### Correcciones manuales auditables

Algunos formatos traen errores que no se pueden resolver leyendo el PDF. Para esos casos existe `data/correcciones.csv`, que el pipeline aplica al final de la corrida.

Dos acciones: `corregir` cambia el valor de una columna en todas las filas de una página, y `agregar` crea una fila nueva tomando el contexto de esa página. Cada línea lleva el motivo, quién la autorizó y la fecha, y cada aplicación queda registrada en el log.

Casos actuales:

| Archivo | Página | Corrección |
|---|---|---|
| Tabla 1 al 331_2026 | 98 | Número de solicitud en cero, corregido a 1289497 |
| UCAP EN VALIDACION_2026 | 245 | Dos ítems colapsados por el PDF, agregados uno por uno |

Corregir esto en el código lo escondería. En este archivo queda visible, versionado y atribuido.

### Caché de extracción

Leer los tres PDF toma varios minutos, y agregar un archivo nuevo no debería obligar a releer los anteriores. El pipeline guarda en `data/cache` la extracción de cada PDF, identificada por nombre, tamaño y fecha de modificación.

Si el PDF no cambió, se reutiliza. Si cambió o es nuevo, se procesa. Después, las reglas que dependen del conjunto completo (deduplicación, correcciones, identificadores) se aplican siempre sobre todos los datos.

El caché lleva además el campo `VERSION_EXTRACCION` de `config.py`. **Cuando se cambie alguna regla de extracción hay que subir ese número**, o el caché seguiría devolviendo datos viejos y el cambio quedaría escondido.

## Problemas del PDF resueltos en el código

### Filas descartadas por bordes faltantes

En algunas páginas la cuadrícula no cierra todas las celdas, y pdfplumber descarta o reubica el texto de las que quedan abiertas. Dos síntomas:

* Fila con cantidad pero sin código ni descripción: el texto se perdió.
* Fila con código y cantidad pero sin descripción: el texto se apiló en la celda de una fila anterior, que queda con dos o tres descripciones concatenadas.

Cuando la tabla detectada presenta cualquiera de los dos, el extractor la reconstruye con cortes explícitos de fila y columna calculados de la geometría de la página. El respaldo se adopta cuando **mejora** la tabla original, no solo cuando la deja perfecta. Como algunas páginas dibujan la cuadrícula con líneas y otras solo con rectángulos, el cálculo de columnas considera ambas fuentes.

### Filas colapsadas que corrompen la cantidad

En un caso de las 968 páginas, dos ítems quedaron fusionados en una sola fila: código `5200501 5200502`, descripciones concatenadas y cantidad `6 1`. El parser de cantidades quitaba el espacio y producía un `61` que no existe en el documento.

Ahora una fila cuyo código contiene un espacio se descarta y se reporta, porque un código UCAP nunca lleva espacios internos. Los ítems reales entran por la tabla de correcciones.

Este caso es el más peligroso de los encontrados: ningún conteo de filas lo detecta, y el valor corrupto se ve perfectamente normal en el CSV.

### Nombres de proyecto partidos en varias líneas

Cuando el nombre no cabe en una línea, el respaldo por coordenadas lo separa en varias filas: el inicio arriba de la etiqueta y la continuación junto a ella o una fila más abajo, con o sin guión de corte.

El extractor reconstruye el nombre uniendo los fragmentos que estén solos en su fila. Las líneas fijas del título del formato se excluyen explícitamente, porque cumplen la misma forma y se pegaban al inicio del nombre.

### Encabezado de columnas partido

La celda dice "Código" en una línea y "UCAP" en la siguiente, y el respaldo las separa. Como el mapa de columnas se busca por el nombre del encabezado y nunca por posición fija, el parser lo maneja sin romperse.

## Hallazgos sobre los documentos

Cuatro números aparecen como SN en un documento y como SS en otro: 1041668, 1097740 y 1097021 entre 2025 y 2026, y 1052703 dentro del mismo PDF de 2026 con contenido idéntico.

Dos números aparecen con obras distintas dentro del mismo PDF, probablemente por error de digitación:

| PDF | Número | Páginas | Proyectos |
|---|---|---|---|
| 2026 | 1265975 | 124 y 125 | Sendero Cl 40 Cr 34 y Callejón Cl 36 B Cr 33 B |
| 2025 | 1159547 | 97 y 118 | SMAP-0221-25 CR 34 CL 10A y Sendero Las Independencias |

En la página 245 del PDF de validación, los códigos `5200501` y `5200502` aparecen asignados al revés que en las más de sesenta filas restantes del histórico, donde `5200501` es la caja de 50x50 cm y `5200502` la directamente enterrada. Está pendiente confirmar cuál asignación es la correcta.

La página 216 del PDF de validación trae encabezado completo pero ninguna línea de detalle. Queda reportada como página sin registros.

El PDF de validación tiene cuatro veces más incidencias por página que los otros dos, lo que sugiere que el formato se depura entre etapas.

## Preguntas abiertas para el área técnica

1. ¿El Consolidado General usa el código con prefijo de retiro o el código base?
2. ¿Qué significan los sufijos con guión en la familia 5200238, y los sufijos `-1` de las hojas de telegestión?
3. ¿Qué es la serie de catorce dígitos que empieza por 5522?
4. ¿La serie de seis dígitos (211xxx, 215xxx, 306xxx) es una familia distinta de materiales?
5. Los 30 ítems escritos con y sin prefijo UCAP, ¿vale la pena corregirlos aguas arriba?
6. ¿Hay más páginas con el número de solicitud errado, además de la 98 de 2026?
7. Los números que aparecen como SN y como SS, ¿son un documento o dos?
8. ¿Cuál es el número correcto de cada obra en los documentos 1265975 (2026) y 1159547 (2025)?
9. ¿Cuál es la asignación correcta de los códigos 5200501 y 5200502?
10. En las cinco páginas repetidas del PDF de validación con contenido distinto, ¿la versión con mayor Colocar es la correcta, o son fases que deberían sumarse?
11. El histórico mezcla documentos de aprobación y de validación. ¿El ETR necesita una columna de estado que los distinga?

## Cómo se valida

La regla del proyecto es que ninguna corrección automática puede esconder pérdida de información. Todo lo que no cuadra se reporta en el log, y el módulo de calidad mide sin corregir.

Antes de dar por bueno un histórico nuevo hay que tomar tres o cuatro documentos al azar con `--resumen`, sumar sus cantidades a mano contra las hojas del PDF y verificar que cuadren. El conteo de filas por sí solo no detecta un desplazamiento de columna ni un separador de miles mal leído.

Cada cambio en la extracción del encabezado se verifica además contra un conjunto fijo de páginas de regresión: 1 y 40 de 2026 (encabezado normal), 296 de 2025 y 328 de 2026 (nombre partido con guión), 132 de validación (nombre partido sin guión) y 245 de validación (descripciones apiladas). Después se revisa el histórico completo en busca de nombres vacíos, muy cortos o que empiecen con texto del título.

Cada incidencia del log empieza con el nombre del archivo y la página, así que se puede filtrar por documento o por tipo.

El CSV se abre en Excel con Datos, Obtener datos, Desde texto/CSV, eligiendo delimitador **Coma** y origen **65001: Unicode (UTF-8)**. Con la configuración regional por defecto, Excel usa punto y coma y desalinea las columnas.

## Limitaciones conocidas

La deduplicación del modo `--append` se apoya en la columna `Fuente`, que contiene el nombre del archivo. Si alguien renombra un PDF ya procesado, sus filas entrarían de nuevo.

La reconstrucción de nombres partidos une como máximo tres fragmentos. Un nombre partido en más líneas quedaría incompleto.

El caché identifica los PDF por nombre, tamaño y fecha. Si llega una versión nueva de un PDF con el mismo nombre, se reprocesa correctamente, pero si se deja la versión vieja al lado de la nueva en la carpeta de entrada, las dos se procesan y se duplican datos.

El correlativo `PROY-n` se recalcula en cada corrida. Un archivo nuevo cuyo nombre quede antes alfabéticamente desplazaría la numeración de los demás.

## Pendientes

1. Confirmar la asignación correcta de los códigos 5200501 y 5200502.
2. Llevar las preguntas abiertas al área técnica y registrar las respuestas en este documento.
3. Definir si se agrega la columna de estado del documento.
4. Conectar el CSV histórico al tablero del ETR.