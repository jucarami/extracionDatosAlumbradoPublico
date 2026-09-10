# Extracción de formatos UCAP AP

Proyecto de extracción de los formatos UCAP AP (EPM, Unidad Alumbrado) desde PDF hacia un CSV histórico que sirva como fuente de datos para el estudio tarifario (ETR) de alumbrado público de Medellín.

Cada página de los PDF contiene un formato con el mismo diseño: un encabezado con el proyecto y su número de solicitud, y una tabla de detalle con los códigos UCAP que se colocan o se quitan. El objetivo es convertir esas páginas en filas, una por código UCAP, con el contexto de la hoja replicado en cada una.

## Estado actual

El proyecto está en construcción. Los módulos de limpieza, configuración y modelo de datos están terminados y probados. La capa de extracción del PDF está a medio camino.

| Módulo | Estado | Qué hace |
|---|---|---|
| `texto.py` | Terminado | Limpieza y normalización de celdas, cantidades y códigos |
| `config.py` | Terminado | Esquema de columnas, rutas y patrones |
| `modelos.py` | Terminado | Representación de un registro y su clave de consolidación |
| `extraccion.py` | En progreso | Detección de tabla, mapeo de columnas y lectura del encabezado |
| `paginas.py` | Pendiente | Reglas de negocio por página e incidencias |
| `pipeline.py` | Pendiente | Recorrido de los PDF y escritura del CSV |
| `calidad.py` | Pendiente | Métricas y reporte de anomalías |
| `cli.py` | Pendiente | Interfaz de línea de comandos |

Al momento hay 48 pruebas automatizadas, todas en verde, que corren sin necesidad de abrir un PDF.

## Estructura

```
alumbradoPublico/
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

Gracias a esa separación, `texto.py` y `modelos.py` no conocen pdfplumber ni pandas, y por eso sus pruebas corren en menos de un segundo.

## Esquema de salida

El CSV tiene once columnas:

| Columna | Origen |
|---|---|
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

## Instalación

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install pdfplumber pandas pytest
```

Para correr las pruebas:

```powershell
pytest -v
```

## Decisiones tomadas

Cada decisión de este apartado se tomó midiendo primero sobre los 723 folios reales de 2025 y 2026, nunca por suposición.

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

### Los ítems sin código no se colapsan

Algunos ítems del formato no tienen código UCAP: crucetas, punta captadora Franklin. Su clave de consolidación queda como `SIN CODIGO` seguido de la descripción normalizada, que es lo que los distingue entre sí. Marcarlos todos con una misma etiqueta genérica los volvería indistinguibles al agrupar, que es un error que ya costó caro antes en este proyecto.

### El número de solicitud no entra en la clave

El número es único en todo el universo de documentos, así que el prefijo SS o SN no aporta nada a la llave. El tipo se conserva en su propia columna para trazabilidad.

## Hallazgos sobre los documentos

Del recorrido completo de los dos PDF salieron varios datos que conviene tener presentes.

Hay 707 números de solicitud únicos repartidos en 723 páginas. La diferencia sugiere que algunos documentos ocupan más de una hoja.

Cuatro números aparecen como SN en 2025 y como SS en 2026, con la misma dirección de proyecto: 1041668, 1097740, 1097021 y 1052703. Coincide con que SS y SN son dos estados de la misma solicitud, así que probablemente sea el mismo trabajo en dos momentos.

La página 98 del PDF de 2026 trae el número de solicitud en cero. Según los registros del área, el número real es 1289497. La corrección no se hace en el código sino en una tabla de correcciones aparte, para que quede auditable quién la autorizó y cuándo.

Dos filas traen la descripción con caracteres entrelazados por texto superpuesto en el PDF: la página 333 de 2025 y la 62 de 2026. Son dos casos de cerca de tres mil, así que se revisan a mano en vez de resolverse en código.

## Preguntas abiertas para el área técnica

1. ¿El Consolidado General usa el código con prefijo de retiro o el código base?
2. ¿Qué significan los sufijos con guión en la familia 5200238?
3. ¿Qué es la serie de catorce dígitos que empieza por 5522?
4. ¿La serie de seis dígitos (211xxx, 215xxx, 306xxx) es una familia distinta de materiales?
5. Los 30 ítems escritos con y sin prefijo UCAP son un problema de captura en el formato origen. ¿Vale la pena corregirlo aguas arriba?
6. ¿Hay más páginas con el número de solicitud errado, además de la 98 de 2026?
7. Los cuatro proyectos que aparecen en ambos años, ¿se cuentan como un documento o como dos?

## Cómo se valida

La regla del proyecto es que ninguna corrección automática puede esconder pérdida de información. Todo lo que no cuadra se reporta en el log de incidencias en vez de arreglarse en silencio.

Antes de dar por bueno el histórico completo hay que tomar tres o cuatro documentos al azar, sumar sus cantidades a mano contra las hojas del PDF y verificar que cuadren. El conteo de filas por sí solo no detecta un desplazamiento de columna.
