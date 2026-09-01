# IMPLEMENTACIÓN — API DataGov (paso a paso)

> **Instrucciones de construcción para el asistente de IA / desarrollador.**
> **Requisito previo obligatorio:** haber leído `CONTEXTO-API-DATAGOV.md`. Este documento
> asume ese contexto y no lo repite.
>
> Stack decidido: **Python 3.11+ y FastAPI**. Despliegue: **contenedor Docker portable**
> (la plataforma final aún no está definida). Acceso a BigQuery: **solo lectura**.

---

## 0. Reglas de trabajo (leer antes de empezar)

1. **Lista blanca obligatoria.** Los datasets que se pueden consultar se declaran en
   configuración. **Jamás** aceptes del cliente un nombre de tabla, un dataset arbitrario
   ni fragmentos de SQL: es la puerta de entrada a inyección SQL y a fuga de información.
2. **Solo lectura.** La cuenta de servicio no debe tener permisos de escritura ni de
   administración sobre BigQuery.
3. **Controla el costo.** BigQuery cobra por datos escaneados. Toda consulta debe tener
   columnas explícitas, filtros y límite de filas. Nunca `SELECT *` sin límite.
4. **Nada de secretos en el código.** Todo por variables de entorno y por la identidad de
   la cuenta de servicio.
5. **Implementa por fases** (sección 8) y verifica cada una antes de seguir.

---

## 1. Estructura del proyecto

```
api-datagov/
├── app/
│   ├── main.py                   # arranque de FastAPI, middlewares, routers
│   ├── config.py                 # variables de entorno + catálogo de datasets permitidos
│   ├── security.py               # autenticación de los consumidores
│   ├── api/
│   │   ├── health.py             # /health y /ready
│   │   ├── datasets.py           # Parte 1: expone datos de la capa Gold
│   │   └── comentarios.py        # Parte 2: ingesta de comentarios desde ValleData
│   ├── services/
│   │   ├── bigquery_repo.py      # consultas de solo lectura a BigQuery
│   │   ├── valledata_client.py   # cliente HTTP hacia la API ValleData
│   │   └── ingesta.py            # orquestación de la recolección de comentarios
│   ├── models/
│   │   └── schemas.py            # modelos Pydantic
│   └── core/
│       ├── logging.py            # logging estructurado en JSON
│       └── errors.py             # manejo uniforme de errores
├── tests/
├── .env.example
├── requirements.txt
├── Dockerfile
└── README.md
```

---

## 2. Dependencias

```
fastapi>=0.110
uvicorn[standard]>=0.29
pydantic>=2.6
pydantic-settings>=2.2
google-cloud-bigquery>=3.20      # cliente oficial de BigQuery
httpx>=0.27                      # cliente HTTP hacia la API ValleData
python-json-logger>=2.0
pytest>=8.0
pytest-asyncio>=0.23
```

---

## 3. Configuración por variables de entorno

```
# Identidad y proyecto GCP
GCP_PROJECT_ID=
BIGQUERY_DATASET_GOLD=
# (las credenciales llegan por la cuenta de servicio del entorno, no por variable)

# Seguridad: token que debe presentar la API ValleData
API_TOKEN=

# Cliente hacia la API ValleData (Parte 2)
VALLEDATA_API_BASE_URL=
VALLEDATA_API_TOKEN=
VALLEDATA_TIMEOUT_SEGUNDOS=30

# Lista blanca de datasets expuestos (Parte 1)
DATASETS_PERMITIDOS_JSON=[{"id":"ventas_2026","tabla":"gold.ventas_2026","columnas":["fecha","municipio","total"],"limite_max":10000}]

# Operación
LOG_LEVEL=INFO
QUERY_TIMEOUT_SEGUNDOS=60
MAX_BYTES_ESCANEADOS=1073741824   # tope de escaneo por consulta (1 GB)
```

La aplicación debe **fallar al arrancar** si falta configuración obligatoria, con un
mensaje claro. En particular, valida que `DATASETS_PERMITIDOS_JSON` tenga forma correcta.

---

## 4. Seguridad

La API atiende a un único consumidor conocido (la API ValleData), así que la superficie
debe ser mínima.

Implementa autenticación por **token bearer** con comparación en tiempo constante
(`secrets.compare_digest`), igual que en la API hermana. Responde **401** con mensaje
genérico ante cualquier fallo, sin revelar la causa. Aplica la protección a todos los
endpoints de datos y deja `/health` y `/ready` públicos.

Si más adelante se decide usar **tokens de identidad de GCP entre servicios** (lo natural
entre dos servicios en la misma nube), implementa la verificación detrás de la misma
dependencia de FastAPI, de modo que cambiar el mecanismo no obligue a tocar los endpoints.

---

## 5. Parte 1 — Exposición de datos de BigQuery

### 5.1 El catálogo de datasets permitidos

Es el corazón de la seguridad de esta API. Cada entrada declara: un **identificador
público** (lo que el consumidor pide), la **tabla real** en BigQuery, las **columnas
autorizadas** y un **límite máximo de filas**.

El consumidor **solo envía el identificador público**. La API lo busca en el catálogo:

- Si **no está**, responde **404** (no reveles qué tablas existen).
- Si **está**, construye la consulta a partir de la definición del catálogo, nunca a
  partir de lo que llegó por la petición.

De esta forma, aunque alguien intente enviar `"tabla": "otra_cosa"` o SQL, no tiene
ningún efecto: ese valor jamás llega a la consulta.

### 5.2 Construcción segura de la consulta

Las columnas y la tabla salen del catálogo (validadas al arrancar). Los **filtros** que
envía el consumidor van siempre como **parámetros de consulta de BigQuery**, nunca
concatenados:

```python
from google.cloud import bigquery

job_config = bigquery.QueryJobConfig(
    query_parameters=[
        bigquery.ScalarQueryParameter("desde", "DATE", desde),
    ],
    maximum_bytes_billed=MAX_BYTES_ESCANEADOS,   # tope de costo
)
```

`maximum_bytes_billed` es una protección importante: si una consulta fuera a escanear más
de lo permitido, BigQuery la **rechaza** en lugar de ejecutarla y generar un costo
inesperado.

Aplica además: columnas explícitas (nunca `SELECT *`), `LIMIT` siempre presente acotado al
`limite_max` del catálogo, y un **timeout** de consulta.

### 5.3 Contrato del endpoint

**`GET /api/v1/datasets/{identificador}`** — protegido por token.

Parámetros: filtros declarados por el catálogo (por ejemplo `desde`, `hasta`,
`municipio`), `limite` y `pagina` o cursor.

Respuesta:

```json
{
  "identificador": "ventas_2026",
  "columnas": ["fecha", "municipio", "total"],
  "datos": [
    {"fecha": "2026-01-15", "municipio": "Alcalá", "total": 1250}
  ],
  "paginacion": {"limite": 1000, "hay_mas": true, "siguiente_cursor": "..."},
  "generado_utc": "2026-08-21T14:00:00Z"
}
```

Adicionalmente, expón **`GET /api/v1/datasets`** para listar los identificadores
disponibles con su descripción y columnas. Es útil para que ValleData sepa qué puede
pedir, sin exponer nombres reales de tablas.

### 5.4 Formato pensado para el destino final

Aunque esta API entrega JSON a la API ValleData, recuerda que el destino último es un
recurso publicado en un portal CKAN. Por eso conviene entregar **estructuras tabulares
planas**: filas homogéneas, sin anidamientos profundos, con nombres de columna estables,
fechas en formato ISO 8601 y valores nulos explícitos. Eso le permite a ValleData
convertir a CSV sin transformaciones complejas y sin generar anomalías de calidad.

### 5.5 Caché

Los datos de la capa Gold no cambian a cada segundo. Considera una **caché en memoria con
tiempo de vida** (por ejemplo 5 a 15 minutos) por combinación de identificador y filtros.
Reduce costos de BigQuery y mejora los tiempos de respuesta. Debe poder desactivarse por
configuración.

---

## 6. Parte 2 — Ingesta de comentarios desde ValleData

### 6.1 Cliente hacia la API ValleData (`valledata_client.py`)

La API ValleData expone los comentarios de los 14 municipios con **paginación por cursor**
(`desde_id`) y **por municipio**. El cliente debe:

- Autenticarse con el token configurado (`VALLEDATA_API_TOKEN`).
- Recorrer **municipio por municipio**, avanzando el cursor hasta agotar los datos.
- Guardar el **último `id` procesado por municipio**, porque los identificadores **no son
  únicos entre municipios**: la clave real es la combinación municipio + id. Confundir
  esto provoca pérdida o duplicación de datos.
- Manejar **timeouts y reintentos** con espera creciente ante errores transitorios (502,
  503, 504), máximo 3 intentos, y no reintentar ante 4xx.
- Revisar el campo **`municipios_con_error`** de la respuesta: si un municipio falló, no
  se debe avanzar su cursor, para reintentarlo en la siguiente ejecución.

### 6.2 Estructura de los datos que llegan

Cada comentario trae: `id`, `municipio`, `dataset_id`, `dataset_nombre`, `usuario`,
`texto_es`, `texto_en` y `creado_utc`. Los textos vienen ya separados por idioma y las
fechas en UTC ISO 8601.

### 6.3 Idempotencia (requisito crítico)

El proceso debe poder ejecutarse varias veces sin duplicar información. Define la clave
única como **`municipio` + `id`** y, al persistir, usa una operación de tipo *merge* /
*upsert* contra la tabla destino. Si el proceso se interrumpe a mitad de camino, la
siguiente ejecución debe retomar desde el último cursor confirmado, sin duplicar lo ya
cargado.

### 6.4 Entrega a los procesos analíticos

**Cómo consumen los DAGs esta información es un punto aún no definido** (ver contexto,
sección 6). Por eso, implementa esta parte también detrás de una interfaz, con dos
posibles estrategias:

- **Modo "pull":** la API expone `GET /api/v1/comentarios` y el DAG la consulta.
- **Modo "push":** la API escribe los comentarios crudos en una tabla intermedia (*staging*)
  de BigQuery y el DAG lee de ahí.

La segunda suele ser la más natural en un ecosistema de analítica, pero **no la des por
decidida**: déjala configurable y consulta al equipo antes de fijarla.

### 6.5 Privacidad

Los comentarios son **contenido escrito por ciudadanos**: son datos personales. No los
registres en los logs, restringe quién puede consultarlos y coordina con el equipo la
política de retención en la tabla destino.

---

## 7. Observabilidad y errores

Aplica el mismo estándar que la API hermana: **logs estructurados en JSON por la salida
estándar**, con marca de tiempo, método, ruta, código de estado, duración e identificador
de correlación (`X-Request-ID`, generado si no viene).

Para las consultas a BigQuery, registra además el identificador del dataset consultado,
las filas devueltas, los **bytes escaneados** y la duración. Los bytes escaneados son el
indicador directo del costo: vigílalos.

**Nunca registres**: el token, credenciales, ni el contenido de los comentarios.

Errores uniformes con la misma forma
(`{"error": ..., "mensaje": ..., "request_id": ...}`) y códigos correctos: **401** sin
credenciales, **404** identificador no permitido o inexistente, **422** parámetros
inválidos, **502** falla la API ValleData, **503** BigQuery no disponible, **500** lo
inesperado. Si BigQuery rechaza una consulta por exceder el tope de bytes, responde un
error claro y explícito, no un 500 genérico.

Incluye `/health` (proceso vivo, sin dependencias) y `/ready` (verifica conectividad con
BigQuery), ambos sin autenticación.

---

## 8. Fases de implementación

**Fase 1 — Esqueleto.** FastAPI que arranca, configuración validada, `/health` y `/ready`,
logging JSON, Dockerfile. *Verificación:* el contenedor levanta y `/health` responde 200.

**Fase 2 — Seguridad.** Token bearer en los endpoints de datos. *Verificación:* sin token
401, con token 200, token ausente de los logs.

**Fase 3 — Catálogo y BigQuery.** Carga y validación del catálogo al arrancar, repositorio
de solo lectura, consulta parametrizada con `maximum_bytes_billed`, timeout y límite.
*Verificación:* un identificador válido devuelve datos; uno no listado devuelve 404; una
consulta que excede el tope se rechaza con error claro.

**Fase 4 — Endpoints de datasets.** `GET /api/v1/datasets` y
`GET /api/v1/datasets/{identificador}` con filtros y paginación. *Verificación:* la
paginación recorre todo el conjunto sin repetir ni omitir filas.

**Fase 5 — Cliente ValleData.** Recorrido por municipio con cursor, timeouts, reintentos y
respeto de `municipios_con_error`. *Verificación:* pruebas con respuestas simuladas
(éxito, timeout, municipio en error) confirmando que los cursores avanzan solo donde
corresponde.

**Fase 6 — Ingesta e idempotencia.** Persistencia con clave `municipio + id` y operación
*upsert*. *Verificación:* ejecutar el proceso dos veces seguidas no duplica registros.

**Fase 7 — Endurecimiento.** Caché, límite de peticiones, documentación OpenAPI revisada,
README y pruebas automatizadas.

---

## 9. Criterios de aceptación

1. Sin token válido, ningún endpoint de datos entrega información (401).
2. Solo se pueden consultar los datasets declarados en la lista blanca; cualquier otro
   identificador responde 404 sin revelar información del esquema.
3. Es **imposible** inyectar SQL o alterar la tabla consultada desde la petición.
4. Toda consulta a BigQuery tiene columnas explícitas, límite, timeout y tope de bytes
   escaneados.
5. Los datos se entregan en estructura tabular plana, con fechas ISO 8601, apta para
   convertirse a CSV sin transformaciones.
6. El cliente de ValleData recorre los 14 municipios manteniendo un **cursor independiente
   por municipio** y no avanza el de los que fallaron.
7. La ingesta es **idempotente**: repetir el proceso no duplica comentarios.
8. Los logs salen en JSON, incluyen bytes escaneados por consulta y **no** contienen
   tokens ni el texto de los comentarios.
9. No hay secretos en el repositorio y la aplicación no arranca mal configurada.
10. Existen pruebas automatizadas de seguridad, lista blanca, paginación e idempotencia.

---

## 10. Errores comunes que debes evitar

Aceptar el nombre de la tabla o filtros SQL desde la petición. Ejecutar `SELECT *` sin
límite (costo descontrolado). Olvidar `maximum_bytes_billed`. Asumir que el `id` de los
comentarios es único entre municipios (provoca pérdida de datos). Avanzar el cursor de un
municipio que falló. Reintentar indefinidamente ante errores 4xx. Registrar el texto de
los comentarios en los logs. Dar a la cuenta de servicio permisos amplios "por comodidad".
Devolver 500 genérico cuando el problema es un tope de costo o una credencial vencida.

---

## 11. Documentos relacionados

- `CONTEXTO-API-DATAGOV.md` — **de lectura obligatoria previa**.
- `CONTEXTO-API-VALLEDATA.md` — el otro lado (incluye la estructura real de los
  comentarios y las restricciones de CKAN).
- `IMPLEMENTACION-API-VALLEDATA.md` — pasos de la API hermana.
- `documentacion/apis_externas.md` — arquitectura aprobada.
