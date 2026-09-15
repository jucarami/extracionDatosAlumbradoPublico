# Extracción de formatos UCAP AP

Proyecto de extracción de los formatos UCAP AP (EPM, Unidad Alumbrado) desde PDF hacia un CSV histórico que sirve como fuente de datos para el estudio tarifario (ETR) de alumbrado público de Medellín.

Cada página de los PDF contiene un formato con el mismo diseño: un encabezado con el proyecto y su número de solicitud, y una tabla de detalle con los códigos UCAP que se colocan o se quitan. El objetivo es convertir esas páginas en filas, una por código UCAP, con el contexto de la hoja replicado en cada una.

## Estado actual

Terminado y validado. Los módulos funcionan y el histórico se extrajo completo de los 723 folios de 2025 y 2026.

| Módulo | Qué hace |
|---|---|
| `texto.py` | Limpieza y normalización de celdas, cantidades, códigos y año |
| `config.py` | Esquema de columnas, rutas y patrones |
| `modelos.py` | Representación de un registro y su clave de consolidación |
| `extraccion.py` | Detección de tabla, mapeo de columnas y lectura del encabezado |
| `paginas.py` | Reglas de negocio por página e incidencias |
| `pipeline.py` | Recorrido de los PDF y escritura del CSV |
| `calidad.py` | Métricas y reporte de anomalías |
| `cli.py` | Interfaz de línea de comandos |

Cifras de la última corrida:

| Métrica | Valor |
|---|---|
| Registros extraídos | 3128 |
| Páginas procesadas | 723 |
| Documentos únicos | 708 |
| UCAP distintos | 147 |
| Registros sin código UCAP | 25 |
| Incidencias reportadas | 25 |
| Pruebas automatizadas | 61 |

## Estructura

```
alumbradoPublico/
├── main.py                punto de entrada
├── src/ucap_etl/          código del paquete
├── tests/                 pruebas automatizadas
├── data/raw/              PDF de entrada (no se versionan)
├── data/processed/        CSV de salida
├── logs/                  reportes de incidencias
└── pyproject.toml         configuración del proyecto
```

Los módulos se organizan de adentro hacia afuera, y ninguno importa a otro que esté a su derecha:

```
texto  →  modelos  →  extraccion  →  paginas  →  pipeline  →  cli
```

Gracias a esa separación, `texto.py` y `modelos.py` no conocen pdfplumber ni pandas, y por eso las 61 pruebas corren en una décima de segundo.

## Instalación

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install pdfplumber pandas pytest
```

## Uso

```powershell
# Procesar todos los PDF de data/raw
python main.py "data/raw/*.pdf" -o data/processed/ucap_historico.csv

# Inspeccionar una página antes de procesar el lote completo
python main.py "data/raw/Tabla 1 al 331_2026.pdf" --debug 40

# Agregar un PDF nuevo al histórico existente, sin duplicar
python main.py "data/raw/nuevo.pdf" --append

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
| `--debug N` | Vuelca la tabla cruda y el contexto de la página N |
| `--resumen` | Imprime los totales por documento |
| `-v` | Salida detallada |

El proceso es idempotente: correrlo dos veces con `--append` sobre los mismos PDF deja el mismo número de filas.

## Esquema de salida

| Columna | Origen |
|---|---|
| `Anio` | Año tomado del nombre del PDF |
| `Pagina` | Número de página dentro del PDF |
| `Tipo` | Literal SS o SN del encabezado |
| `SS/SN` | Número de solicitud que aparece a la derecha del literal |
| `Proyecto` | Texto que sigue a la etiqueta "Proyecto:" |
| `codigo UCAP` | Primera columna del detalle, si cumple el patrón de código |
| `Descripcion UCAP` | Segunda columna, texto crudo tal como aparece en el documento |
| `Colocar` | Tercera columna, convertida a número |
| `Quitar` | Cuarta columna, convertida a número |
| `Descripcion Normalizada` | Descripción canónica para cruzar contra el catálogo |
| `Fuente` | Nombre del archivo y página de origen |
| `Clave Consolidacion` | Llave hacia el catálogo de UCAP |

## Decisiones tomadas

Cada decisión de este apartado se tomó midiendo primero sobre los 723 folios reales, nunca por suposición.

### El código UCAP se conserva tal como viene

En los documentos aparecen varias formas de código: numéricos de siete dígitos como `5200272`, con prefijo de letra como `R5200219` donde la R marca retiro, con sufijo como `5200238-3`, de seis dígitos como `211332`, y de catorce dígitos como `55220000446149`.

Todos se guardan crudos. Quitar el prefijo o el sufijo sería una transformación irreversible: si dos códigos que parecían iguales resultan ser ítems distintos, ya no hay manera de separarlos. Al revés siempre se puede, porque teniendo el código completo derivar el base es trivial.

Los casos de seis y catorce dígitos se inspeccionaron uno por uno. Todos traen descripción y cantidad válidas, así que se aceptan.

### El prefijo UCAP se retira de la descripción normalizada

De las 67 descripciones que empiezan por la palabra UCAP, 30 existen también escritas sin ese prefijo para el mismo ítem. Por ejemplo `UCAP POSTE CONCRETO OCTOG 12M` y `POSTE CONCRETO OCTOG 12M` aparecen ambas en los documentos.

Es inconsistencia de digitación, no información. Si no se unifica, esos 30 ítems quedan partidos en dos al agrupar.

La columna `Descripcion UCAP` conserva el texto crudo con prefijo. Solo la columna normalizada lo pierde. Por eso existen las dos.

### Una celda vacía no es un cero

Cuando la columna Colocar viene vacía significa que ese UCAP no se coloca, se quita. Escribir cero ahí produciría miles de valores falsos al promediar o contar en el tablero. El vacío se conserva como nulo.

Las cantidades se escriben al CSV como texto formateado, porque pandas promueve la columna a decimal al mezclar enteros con nulos y escribiría `4.0` donde el formato dice `4`.

### Los ítems sin código no se colapsan

Algunos ítems del formato no tienen código UCAP: crucetas, punta captadora Franklin. Su clave de consolidación queda como `SIN CODIGO` seguido de la descripción normalizada, que es lo que los distingue entre sí. Marcarlos todos con una misma etiqueta genérica los volvería indistinguibles al agrupar, que es un error que ya costó caro antes en este proyecto.

### El número de solicitud no entra en la clave

El número es único en todo el universo de documentos, así que el prefijo SS o SN no aporta nada a la llave. El tipo se conserva en su propia columna para trazabilidad.

### Las anotaciones no entran al histórico

Algunos formatos traen notas escritas a mano en la columna de descripción: comentarios del técnico, subtítulos de sección, observaciones sobre el modelo digital. No tienen código ni cantidad en ninguna columna, así que no son materiales y se descartan. Cada una queda reportada en el log de incidencias con su página.

### Un reemplazo es una sola fila

Cerca del ocho por ciento de los registros trae cantidad en Colocar y en Quitar a la vez. Son reemplazos: se retiran unidades viejas y se colocan nuevas del mismo ítem. Es una operación normal del negocio y así viene en el formato, de modo que se guarda tal cual, en una sola fila. La propiedad `movimiento` la clasifica como AMBOS.

### El año viene del nombre del archivo

Es una convención de nombrado, no un dato del formato. Si el archivo no lo trae, la columna queda vacía y el pipeline lo reporta como incidencia en vez de asumir un año.

## Problemas del PDF resueltos en el código

### Filas descartadas por bordes faltantes

En algunas páginas la cuadrícula del formato no cierra todas las celdas, y pdfplumber descarta el texto de las que quedan abiertas. Eso hacía perder filas completas que sí están en el documento: veinticinco en total, entre ellas códigos UCAP con su cantidad.

Cuando la tabla detectada trae filas con cantidad pero sin código ni descripción, el extractor la reconstruye con cortes explícitos de fila y columna, calculados de la propia geometría de la página. El respaldo solo se adopta si efectivamente arregla el problema.

Algunas páginas dibujan la cuadrícula con líneas y otras solo con rectángulos, así que el cálculo de columnas considera ambas fuentes.

### Nombres de proyecto partidos en dos líneas

Cuando el nombre del proyecto no cabe en una línea, el respaldo por coordenadas lo separa en dos filas y solo una queda junto a la etiqueta. El extractor lo reconstruye uniendo el fragmento anterior, que siempre termina en guión, con la continuación.

### Encabezado de columnas partido

La celda del encabezado dice "Código" en una línea y "UCAP" en la siguiente. El respaldo por coordenadas las separa, y por eso el índice de la fila de encabezados cambia de página a página. Como el mapa de columnas se busca por el nombre del encabezado y nunca por posición fija, el parser lo maneja sin romperse.

## Hallazgos sobre los documentos

Hay 708 números de solicitud únicos repartidos en 723 páginas. La diferencia sugiere que algunos documentos ocupan más de una hoja.

Cuatro números aparecen como SN en 2025 y como SS en 2026, con la misma dirección de proyecto: 1041668, 1097740, 1097021 y 1052703. Coincide con que SS y SN son dos estados de la misma solicitud, así que probablemente sea el mismo trabajo en dos momentos.

La página 98 del PDF de 2026 trae el número de solicitud en cero. Según los registros del área, el número real es 1289497. La corrección no se hace en el código sino en una tabla de correcciones aparte, todavía pendiente, para que quede auditable quién la autorizó y cuándo.

Dos filas traen la descripción con caracteres entrelazados por texto superpuesto en el PDF: la página 333 de 2025 y la 62 de 2026. Son dos casos de más de tres mil, así que se revisan a mano en vez de resolverse en código.

La página 301 de 2025 trae el nombre del proyecto con marcas `(cid:9)`, que son caracteres que pdfplumber no pudo mapear a una fuente. Afecta el nombre, no los datos.

## Preguntas abiertas para el área técnica

1. ¿El Consolidado General usa el código con prefijo de retiro o el código base?
2. ¿Qué significan los sufijos con guión en la familia 5200238?
3. ¿Qué es la serie de catorce dígitos que empieza por 5522?
4. ¿La serie de seis dígitos (211xxx, 215xxx, 306xxx) es una familia distinta de materiales?
5. Los 30 ítems escritos con y sin prefijo UCAP son un problema de captura en el formato origen. ¿Vale la pena corregirlo aguas arriba?
6. ¿Hay más páginas con el número de solicitud errado, además de la 98 de 2026?
7. Los cuatro proyectos que aparecen en ambos años, ¿se cuentan como un documento o como dos?
8. Los reemplazos donde un mismo ítem se coloca y se quita en la misma línea, ¿deben quedar como una fila o desagregarse en dos?

## Cómo se valida

La regla del proyecto es que ninguna corrección automática puede esconder pérdida de información. Todo lo que no cuadra se reporta en el log de incidencias en vez de arreglarse en silencio, y el módulo de calidad mide sin corregir.

Antes de dar por bueno un histórico nuevo hay que tomar tres o cuatro documentos al azar con `--resumen`, sumar sus cantidades a mano contra las hojas del PDF y verificar que cuadren. El conteo de filas por sí solo no detecta un desplazamiento de columna ni un separador de miles mal leído.

El histórico actual se validó de esa forma contra cuatro documentos, y los cuatro cuadran.

## Limitaciones conocidas

La deduplicación del modo `--append` se apoya en la columna `Fuente`, que contiene el nombre del archivo. Si alguien renombra un PDF ya procesado, sus filas entrarían de nuevo como si fueran distintas.

La reconstrucción de nombres de proyecto partidos cubre el corte en dos líneas marcado con guión final. Un nombre partido en tres líneas, o cortado sin guión, quedaría incompleto.

## Pendientes

1. Construir la tabla de correcciones auditable, con la página 98 de 2026 como primer caso.
2. Llevar las preguntas abiertas al área técnica y registrar las respuestas en este documento.
3. Conectar el CSV histórico al tablero del ETR.
