# Extracción de formatos UCAP AP

Proyecto de extracción de los formatos UCAP AP (EPM, Unidad Alumbrado) desde PDF hacia un CSV histórico que sirve como fuente de datos para el estudio tarifario (ETR) de alumbrado público de Medellín.

Cada página de los PDF contiene un formato con el mismo diseño: un encabezado con el proyecto y su número de solicitud, y una tabla de detalle con los códigos UCAP que se colocan o se quitan. El objetivo es convertir esas páginas en filas, una por código UCAP, con el contexto de la hoja replicado en cada una.

## Estado actual

Terminado y validado sobre tres documentos fuente.

| PDF | Páginas | Contenido |
|---|---|---|
| `Tablas 1 al 392_2025.pdf` | 392 | Formatos de 2025 |
| `Tabla 1 al 331_2026.pdf` | 331 | Formatos de 2026 |
| `UCAP EN VALIDACION DE APROBACION_2026.pdf` | 245 | Formatos en validación de aprobación, 2026 |

| Módulo | Qué hace |
|---|---|
| `texto.py` | Limpieza y normalización de celdas, cantidades, códigos y año |
| `config.py` | Esquema de columnas, rutas, patrones y títulos fijos del formato |
| `modelos.py` | Representación de un registro y su clave de consolidación |
| `extraccion.py` | Detección de tabla, mapeo de columnas y lectura del encabezado |
| `paginas.py` | Reglas de negocio por página, herencia de encabezado e incidencias |
| `pipeline.py` | Recorrido de los PDF, deduplicación de páginas y escritura del CSV |
| `calidad.py` | Métricas y reporte de anomalías |
| `cli.py` | Interfaz de línea de comandos |

Cifras de la última corrida:

| Métrica | Valor |
|---|---|
| Registros extraídos | 4109 |
| Páginas conservadas | 937 de 968 |
| Documentos únicos | 923 |
| UCAP distintos | 175 |
| Registros sin código UCAP | 32 |
| Páginas descartadas por duplicado | 30 |
| Incidencias reportadas | 86 |
| Pruebas automatizadas | 73 |

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

Gracias a esa separación, `texto.py` y `modelos.py` no conocen pdfplumber ni pandas, y por eso las pruebas corren en menos de un segundo.

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
python main.py "data/raw/nuevo_2026.pdf" --append

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

Cuando cambian las reglas de extracción o de deduplicación, el histórico se regenera completo desde todos los PDF, sin `--append`.

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

Cada decisión de este apartado se tomó midiendo primero sobre los folios reales, nunca por suposición.

### El código UCAP se conserva tal como viene

En los documentos aparecen varias formas de código: numéricos de siete dígitos como `5200272`, con prefijo de letra como `R5200219` donde la R marca retiro, con sufijo como `5200238-3` o `5200207-1`, de seis dígitos como `211332`, y de catorce dígitos como `55220000446149`.

Todos se guardan crudos. Quitar el prefijo o el sufijo sería una transformación irreversible: si dos códigos que parecían iguales resultan ser ítems distintos, ya no hay manera de separarlos. Al revés siempre se puede.

### El prefijo UCAP se retira de la descripción normalizada

De las 67 descripciones de 2025 y 2026 que empiezan por la palabra UCAP, 30 existen también escritas sin ese prefijo para el mismo ítem. Es inconsistencia de digitación, no información, y si no se unifica esos ítems quedan partidos en dos al agrupar.

La columna `Descripcion UCAP` conserva el texto crudo con prefijo. Solo la columna normalizada lo pierde.

### Una celda vacía no es un cero

Cuando la columna Colocar viene vacía significa que ese UCAP no se coloca, se quita. Escribir cero ahí produciría valores falsos al promediar o contar en el tablero. El vacío se conserva como nulo.

Las cantidades se escriben al CSV como texto formateado, porque pandas promueve la columna a decimal al mezclar enteros con nulos y escribiría `4.0` donde el formato dice `4`.

### Los ítems sin código no se colapsan

Crucetas, punta captadora Franklin y otros ítems sin código UCAP llevan como clave `SIN CODIGO` seguido de la descripción normalizada, que es lo que los distingue entre sí. Marcarlos todos con una etiqueta genérica los volvería indistinguibles al agrupar.

### El número de solicitud no entra en la clave

El número es único en el universo de documentos, así que el prefijo SS o SN no aporta a la llave. El tipo se conserva en su propia columna para trazabilidad.

### Las anotaciones no entran al histórico

Notas escritas a mano en la columna de descripción, subtítulos de sección y comentarios del técnico no tienen código ni cantidad, así que se descartan. Cada una queda en el log de incidencias con su página.

### Un reemplazo es una sola fila

Cerca del ocho por ciento de los registros trae cantidad en Colocar y en Quitar a la vez. Son reemplazos: se retiran unidades viejas y se colocan nuevas del mismo ítem. Se guardan tal como vienen, en una sola fila, y la propiedad `movimiento` los clasifica como AMBOS.

### El año viene del nombre del archivo

Es una convención de nombrado, no un dato del formato. Si el archivo no lo trae, la columna queda vacía y el pipeline lo reporta. Por eso el PDF de validación se renombró agregando `_2026` al final.

### Una página hereda encabezado solo si no trae nada propio

Si una hoja no trae ni proyecto ni número de solicitud, se considera continuación de la anterior y hereda su encabezado. Si trae cualquiera de los dos, es un documento distinto: sus datos faltantes se reportan como encabezado incompleto y nunca se rellenan con los de otra hoja.

Esta regla falló dos veces en direcciones opuestas antes de quedar así. En las hojas de telegestión el nombre no se leía completo pero el número era propio, y heredaban un número ajeno. En la página 98 de 2026 el número venía en cero pero el proyecto era propio, y heredaba el proyecto de la página anterior. Ambos casos tienen prueba automatizada.

### Deduplicación de páginas repetidas

Regla confirmada por el área técnica: si dentro de un mismo PDF un documento aparece en varias páginas con el mismo número y el mismo proyecto, es duplicación del formato, y se conserva la página con mayor suma en Colocar. En empate gana la de menor número de página.

Tres límites de la regla:

1. **Cada PDF se evalúa solo contra sí mismo.** Un documento que aparece en 2025 y en validación 2026 se conserva en ambos, porque puede ser el mismo trabajo en dos estados.
2. **Si el número se repite con proyectos distintos, no es duplicado.** Es un probable error de digitación del número: se conservan todas las páginas y se reporta para corregirlo en el origen.
3. **Los SS distintos se conservan aunque compartan estructura.** Es común que un formato se copie del diseño del proyecto anterior.

El nombre del proyecto se compara sin tildes, mayúsculas ni comas, para que `Vía CR 81` y `VIA CR 81,` cuenten como el mismo.

De las 30 páginas descartadas, 25 son copias idénticas. Las otras cinco, todas del PDF de validación, tienen el mismo proyecto pero contenido distinto, y quedan listadas en el log con el conteo de ítems de ambas páginas.

## Problemas del PDF resueltos en el código

### Filas descartadas por bordes faltantes

En algunas páginas la cuadrícula no cierra todas las celdas, y pdfplumber descarta el texto de las que quedan abiertas. Eso hacía perder filas completas que sí están en el documento.

Cuando la tabla detectada trae filas con cantidad pero sin código ni descripción, el extractor la reconstruye con cortes explícitos de fila y columna, calculados de la geometría de la página. El respaldo solo se adopta si efectivamente arregla el problema. Como algunas páginas dibujan la cuadrícula con líneas y otras solo con rectángulos, el cálculo de columnas considera ambas fuentes.

### Nombres de proyecto partidos en varias líneas

Cuando el nombre no cabe en una línea, el respaldo por coordenadas lo separa en varias filas. El fragmento inicial queda arriba de la etiqueta "Proyecto:" y la continuación junto a ella o una fila más abajo, con o sin guión de corte.

El extractor reconstruye el nombre uniendo los fragmentos que estén solos en su fila. Las líneas fijas del título del formato (`EMPRESAS PÚBLICAS DE MEDELLÍN`, `UNIDAD ALUMBRADO`, `UCAP AP`) se excluyen explícitamente, porque cumplen la misma forma y se pegaban al inicio del nombre.

### Encabezado de columnas partido

La celda del encabezado dice "Código" en una línea y "UCAP" en la siguiente, y el respaldo por coordenadas las separa. Como el mapa de columnas se busca por el nombre del encabezado y nunca por posición fija, el parser lo maneja sin romperse.

## Hallazgos sobre los documentos

Cuatro números aparecen como SN en un documento y como SS en otro: 1041668, 1097740 y 1097021 entre 2025 y 2026, y 1052703 dentro del mismo PDF de 2026 (págs 61 y 269) con contenido idéntico.

La página 98 del PDF de 2026 trae el número de solicitud en cero. Según los registros del área, el número real es 1289497. La corrección va en una tabla de correcciones aparte, todavía pendiente, para que quede auditable.

Dos números aparecen con obras distintas dentro del mismo PDF, probablemente por error de digitación:

| PDF | Número | Páginas | Proyectos |
|---|---|---|---|
| 2026 | 1265975 | 124 y 125 | Sendero Cl 40 Cr 34 y Callejón Cl 36 B Cr 33 B |
| 2025 | 1159547 | 97 y 118 | SMAP-0221-25 CR 34 CL 10A y Sendero Las Independencias |

La página 216 del PDF de validación trae encabezado completo pero ninguna línea de detalle. Queda reportada como página sin registros.

Dos filas traen la descripción con caracteres entrelazados por texto superpuesto: la página 333 de 2025 y la 62 de 2026. La página 301 de 2025 trae marcas `(cid:9)` en el nombre del proyecto. Afectan texto, no cantidades.

## Preguntas abiertas para el área técnica

1. ¿El Consolidado General usa el código con prefijo de retiro o el código base?
2. ¿Qué significan los sufijos con guión en la familia 5200238, y los sufijos `-1` de las hojas de telegestión?
3. ¿Qué es la serie de catorce dígitos que empieza por 5522?
4. ¿La serie de seis dígitos (211xxx, 215xxx, 306xxx) es una familia distinta de materiales?
5. Los 30 ítems escritos con y sin prefijo UCAP, ¿vale la pena corregirlos aguas arriba?
6. ¿Hay más páginas con el número de solicitud errado, además de la 98 de 2026?
7. Los números que aparecen como SN y como SS, ¿son un documento o dos?
8. ¿Cuál es el número correcto de cada obra en los documentos 1265975 (2026) y 1159547 (2025)?
9. En las cinco páginas repetidas del PDF de validación con contenido distinto (1078189, 1079802, 1343500, 1348589, 1353315), ¿la versión con mayor Colocar es la correcta, o son fases que deberían sumarse?
10. El histórico mezcla documentos de aprobación y de validación. ¿El ETR necesita una columna de estado que los distinga?

## Cómo se valida

La regla del proyecto es que ninguna corrección automática puede esconder pérdida de información. Todo lo que no cuadra se reporta en el log de incidencias, y el módulo de calidad mide sin corregir.

Antes de dar por bueno un histórico nuevo hay que tomar tres o cuatro documentos al azar con `--resumen`, sumar sus cantidades a mano contra las hojas del PDF y verificar que cuadren. El conteo de filas por sí solo no detecta un desplazamiento de columna ni un separador de miles mal leído.

Cada cambio en la extracción del encabezado se verifica además contra un conjunto fijo de páginas de regresión: 1 y 40 de 2026 (encabezado normal), 296 de 2025 y 328 de 2026 (nombre partido con guión), y 132 de validación (nombre partido sin guión). Después se revisa el histórico completo en busca de nombres vacíos, muy cortos o que empiecen con texto del título.

## Limitaciones conocidas

La deduplicación del modo `--append` se apoya en la columna `Fuente`, que contiene el nombre del archivo. Si alguien renombra un PDF ya procesado, sus filas entrarían de nuevo.

La reconstrucción de nombres partidos une como máximo tres fragmentos: el de arriba, el de la etiqueta y el de abajo. Un nombre partido en más líneas quedaría incompleto.

La deduplicación compara proyectos normalizados. Si dos páginas del mismo documento escriben el proyecto de forma sustancialmente distinta, se tratan como obras distintas y se reportan como posible error de digitación en vez de descartarse.

## Pendientes

1. Construir la tabla de correcciones auditable, con la página 98 de 2026 como primer caso.
2. Llevar las preguntas abiertas al área técnica y registrar las respuestas en este documento.
3. Definir si se agrega la columna de estado del documento.
4. Conectar el CSV histórico al tablero del ETR.