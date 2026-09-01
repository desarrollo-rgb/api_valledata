# IMPLEMENTACIÓN — API ValleData (paso a paso)

> **Instrucciones de construcción para el asistente de IA / desarrollador.**
> **Requisito previo obligatorio:** haber leído `CONTEXTO-API-VALLEDATA.md`. Este
> documento asume ese contexto y no lo repite.
>
> Stack decidido: **Python 3.11+ y FastAPI**. Despliegue: **contenedor Docker portable**
> (la plataforma final aún no está definida). Base de datos: **solo lectura**.

---

## 0. Reglas de trabajo (leer antes de empezar)

1. **No inventes contratos ajenos.** El contrato de la API DataGov (Parte 1) todavía no
   está definido. Constrúyelo detrás de una **interfaz/adaptador** para poder cambiarlo
   sin tocar el resto del código, y trabaja con un *mock* mientras tanto.
2. **La API solo lee de PostgreSQL.** Nunca `INSERT`, `UPDATE` ni `DELETE` sobre las bases
   de los portales. El usuario de base de datos debe ser de **solo lectura**.
3. **Nada de secretos en el código.** Todo por variables de entorno. Ni cadenas de
   conexión, ni tokens, ni credenciales, ni siquiera en los ejemplos de prueba.
4. **Nunca aceptes SQL ni nombres de tabla desde el exterior.** Usa siempre consultas
   parametrizadas.
5. **Implementa por fases** (sección 8) y verifica cada una antes de seguir.

---

## 1. Estructura del proyecto

Crea el repositorio con esta estructura. Es una organización estándar de FastAPI, pensada
para que cada pieza tenga una única responsabilidad:

```
api-valledata/
├── app/
│   ├── main.py                  # arranque de FastAPI, middlewares, routers
│   ├── config.py                # carga y valida variables de entorno
│   ├── security.py              # autenticación por token (bearer)
│   ├── api/
│   │   ├── health.py            # /health y /ready
│   │   ├── comentarios.py       # Parte 2: expone comentarios a DataGov
│   │   └── datasets.py          # Parte 1: republica datos de DataGov para CKAN
│   ├── services/
│   │   ├── comentarios_repo.py  # acceso de solo lectura a PostgreSQL (multi-tenant)
│   │   ├── datagov_client.py    # cliente HTTP hacia la API DataGov (adaptador)
│   │   └── formatters.py        # conversión a CSV / JSON / GeoJSON para CKAN
│   ├── models/
│   │   └── schemas.py           # modelos Pydantic (contratos de entrada y salida)
│   └── core/
│       ├── logging.py           # logging estructurado en JSON
│       └── errors.py            # manejo uniforme de errores
├── tests/
│   ├── test_comentarios.py
│   ├── test_datasets.py
│   └── test_security.py
├── .env.example                 # plantilla de variables (SIN valores reales)
├── requirements.txt
├── Dockerfile
├── docker-compose.yml           # entorno local con un PostgreSQL de pruebas
└── README.md
```

---

## 2. Dependencias

En `requirements.txt`:

```
fastapi>=0.110
uvicorn[standard]>=0.29
pydantic>=2.6
pydantic-settings>=2.2
psycopg[binary,pool]>=3.1       # driver PostgreSQL con pool de conexiones
httpx>=0.27                     # cliente HTTP para llamar a la API DataGov
python-json-logger>=2.0         # logs en JSON
pytest>=8.0                     # pruebas
pytest-asyncio>=0.23
```

Usa **psycopg 3** (no psycopg2): tiene mejor soporte de *connection pooling* y de
`async`, que es justo lo que necesita una API multi-tenant.

---

## 3. Configuración por variables de entorno

Todo se configura por entorno. Crea `.env.example` como plantilla (nunca con valores
reales) y en `app/config.py` valida la configuración al arrancar con `pydantic-settings`.

Variables necesarias:

```
# Seguridad: token que deben presentar los consumidores (CKAN y API DataGov)
API_TOKEN=

# Conexión a los portales (multi-tenant). Un JSON con la lista de municipios.
# Cada entrada: código del municipio y su cadena de conexión de solo lectura.
MUNICIPIOS_JSON=[{"codigo":"alcala","nombre":"Alcalá","dsn":"postgresql://usuario_ro:clave@host:5432/ckan_alcala"}]

# Cliente hacia la API DataGov (Parte 1)
DATAGOV_API_BASE_URL=
DATAGOV_API_TOKEN=
DATAGOV_TIMEOUT_SEGUNDOS=30

# Operación
LOG_LEVEL=INFO
MAX_PAGE_SIZE=1000
DEFAULT_PAGE_SIZE=100
```

**Regla importante:** la aplicación debe **fallar al arrancar** si falta una variable
obligatoria (por ejemplo `API_TOKEN`), con un mensaje claro. Es preferible no levantar a
levantar mal configurada.

---

## 4. Seguridad (`app/security.py`)

La autenticación es por **token bearer**, porque es uno de los cuatro modos que CKAN
soporta al consumir endpoints externos (ver contexto, sección 3.4).

Implementa una dependencia de FastAPI que:

1. Lee la cabecera `Authorization: Bearer <token>`.
2. Compara el token con el configurado usando **comparación en tiempo constante**
   (`secrets.compare_digest`), para evitar ataques de temporización.
3. Si falta la cabecera o el token no coincide, responde **401** con un mensaje genérico
   (`{"error": "unauthorized"}`), **sin revelar** si el token existe o por qué falló.
4. Se aplica a **todos** los endpoints de datos. Los endpoints `/health` y `/ready` quedan
   públicos, porque los usan los chequeos de la plataforma.

Adicionalmente:

- **Nunca registres el token en los logs**, ni completo ni parcial.
- Aplica **HTTPS siempre** en producción (lo resuelve la plataforma de despliegue).
- Considera un **límite de peticiones** (por ejemplo 60 por minuto por token) para
  proteger la base de datos ante consumos anómalos.

---

## 5. Parte 2 — Endpoint de comentarios (empieza por aquí)

Este es el flujo con requisitos más claros y verificados, por eso se implementa primero.

### 5.1 Consulta SQL base

La tabla y sus columnas están descritas en el contexto (sección 4). La consulta debe ser
**parametrizada** y usar `id` como cursor de paginación:

```sql
SELECT id, "package_Id", comment, user_id, created
FROM comments
WHERE id > %(cursor)s
ORDER BY id ASC
LIMIT %(limite)s;
```

Detalles que no se pueden omitir:

- **`"package_Id"` va entre comillas dobles** porque tiene mayúscula; sin comillas,
  PostgreSQL lo interpreta en minúsculas y la consulta falla.
- Si se requiere filtrar por fecha, añade `AND created >= %(desde)s` — siempre
  parametrizado, nunca concatenando texto.
- No uses `OFFSET` para paginar: con volúmenes altos degrada el rendimiento y puede
  saltarse o repetir filas si hay inserciones concurrentes.

### 5.2 Enriquecimiento opcional del dataset

Si se requiere el nombre o título del dataset (no solo su identificador), se puede unir
con la tabla `package` de CKAN:

```sql
SELECT c.id, c."package_Id", c.comment, c.user_id, c.created,
       p.name AS package_name, p.title AS package_title
FROM comments c
LEFT JOIN package p ON p.id = c."package_Id"
WHERE c.id > %(cursor)s
ORDER BY c.id ASC
LIMIT %(limite)s;
```

Usa `LEFT JOIN` (no `INNER`) para que un comentario no desaparezca si su dataset fue
borrado.

### 5.3 Transformación del campo `comment`

El campo viene como JSON serializado `{"en": "...", "es": "..."}`. La API debe:

1. Intentar `json.loads()`.
2. Si funciona y es un diccionario, extraer `es` y `en`.
3. **Si falla o no es un diccionario** (filas antiguas con texto plano), no lanzar
   excepción: usar el texto tal cual como valor en español y dejar el inglés en `null`.

Esta tolerancia es obligatoria; una excepción aquí tumbaría la extracción completa.

### 5.4 Contrato del endpoint

**`GET /api/v1/comentarios`** — protegido por token.

Parámetros de consulta:

- `municipio` (opcional): código del municipio. Si se omite, devuelve de **todos**.
- `desde_id` (opcional, por defecto `0`): cursor de paginación incremental.
- `desde_fecha` (opcional): filtro por fecha mínima, en ISO 8601 UTC.
- `limite` (opcional, por defecto `DEFAULT_PAGE_SIZE`, máximo `MAX_PAGE_SIZE`).

Respuesta:

```json
{
  "datos": [
    {
      "id": 20,
      "municipio": "alcala",
      "dataset_id": "a279e649-55d8-49f8-a50e-509efff83cf2",
      "dataset_nombre": "territorio-dataset",
      "usuario": "admin",
      "texto_es": "Buen conjunto de datos",
      "texto_en": "Good dataset",
      "creado_utc": "2026-08-11T15:34:10Z"
    }
  ],
  "paginacion": {
    "siguiente_desde_id": 20,
    "limite": 100,
    "hay_mas": true
  },
  "municipios_con_error": []
}
```

Puntos clave del contrato:

- **`id` no es único entre municipios** (cada base tiene su propia secuencia). Por eso el
  campo `municipio` es obligatorio en cada registro, y la clave real del comentario es la
  **combinación municipio + id**.
- Cuando se consultan varios municipios a la vez, la paginación por cursor debe manejarse
  **por municipio**. La forma más simple y robusta es que el consumidor itere municipio
  por municipio (`?municipio=alcala&desde_id=...`). Documenta esto explícitamente.
- **`municipios_con_error`** lista los municipios que no respondieron. Es la
  materialización del requisito de tolerancia a fallos parciales: si una base está caída,
  la respuesta **no falla**, entrega lo que pudo y reporta el problema.
- Las fechas se entregan en **UTC ISO 8601 con sufijo `Z`**.

### 5.5 Manejo de las 14 conexiones

Crea **un pool de conexiones por municipio**, inicializado de forma perezosa (solo al
usarse por primera vez). Configura un **timeout corto** de conexión y de consulta
(por ejemplo 10 segundos) para que un municipio lento no bloquee toda la respuesta.
Envuelve cada consulta en su propio `try/except`: un fallo se registra, se añade a
`municipios_con_error` y el proceso continúa con los demás.

---

## 6. Parte 1 — Republicación de datos para CKAN

### 6.1 Cliente hacia la API DataGov (`datagov_client.py`)

Como el contrato de DataGov no está definido, implementa un **adaptador** con una
interfaz mínima y estable, por ejemplo un método `obtener_dataset(identificador, filtros)`
que devuelva filas normalizadas. Detrás de esa interfaz pon la llamada HTTP real con
`httpx`, incluyendo:

- Cabecera de autenticación hacia DataGov (según lo que se acuerde).
- **Timeout** explícito (`DATAGOV_TIMEOUT_SEGUNDOS`).
- **Reintentos** con espera creciente para errores transitorios (502, 503, 504 y timeouts),
  máximo 3 intentos. **Nunca reintentes** ante 4xx: son errores del cliente y reintentar
  no los arregla.
- Traducción de errores de DataGov a errores propios, sin filtrar detalles internos del
  otro proyecto hacia CKAN.

Mientras el contrato real no exista, provee una implementación *mock* activable por
configuración, para poder desarrollar y probar todo el flujo.

### 6.2 Endpoint que consumirá CKAN

**`GET /api/v1/datasets/{identificador}.{formato}`** — protegido por token.

Donde `formato` es **`csv`**, **`json`** o **`geojson`**. Esta forma de ruta (con la
extensión al final) es deliberada: según el contexto (sección 3.3), CKAN detecta el
formato primero por la extensión de la URL, así que esto elimina toda ambigüedad.

Requisitos de la respuesta, que vienen de cómo funciona CKAN:

- **`Content-Type` correcto y explícito**: `text/csv; charset=utf-8` para CSV,
  `application/json` para JSON, `application/geo+json` para GeoJSON.
- Añade la cabecera `Content-Disposition: attachment; filename="<nombre>.<ext>"`, para que
  el archivo quede con un nombre razonable.
- El CSV debe llevar **encabezados en la primera fila**, codificación **UTF-8** y
  separador coma.
- Si el volumen es grande, responde con **streaming** (`StreamingResponse`) en lugar de
  armar todo el contenido en memoria.

### 6.3 Calidad de los datos que se entregan a CKAN

Los portales analizan automáticamente los archivos que ingieren y **advierten al
administrador si detectan anomalías**. Para que los recursos publicados no lleguen con
advertencias, la API debe cuidar que:

- Los **encabezados no se repitan** y no tengan espacios sobrantes.
- Cada fila tenga **exactamente el mismo número de columnas** que el encabezado.
- Las **fechas** usen un **único formato consistente** (se recomienda ISO 8601).
- Los **booleanos** sean consistentes (siempre `true`/`false`, no mezclar con `sí`/`no`).
- El texto no traiga **caracteres corruptos**: fuerza UTF-8 de extremo a extremo.
- Los valores no lleven espacios en blanco al inicio o al final.

Estas reglas no son opcionales: replican exactamente lo que el validador de calidad del
portal revisa.

---

## 7. Observabilidad y errores

### 7.1 Logging estructurado

Emite los logs en **JSON por la salida estándar** (una línea por evento). Es el mismo
patrón que ya usa el portal, y permite que la plataforma de nube los recoja y los indexe
automáticamente.

Cada petición debe registrar: marca de tiempo, método, ruta, código de estado, duración en
milisegundos, municipio consultado (si aplica), número de registros devueltos y un
identificador de correlación.

**Nunca registres**: el token de autenticación, cadenas de conexión, ni el contenido de
los comentarios (son datos de ciudadanos).

### 7.2 Identificador de correlación

Acepta la cabecera `X-Request-ID`; si no viene, genera un UUID. Inclúyelo en todos los
logs de esa petición y devuélvelo en la respuesta. Esto permite rastrear una misma
operación a través de CKAN, API ValleData y API DataGov.

### 7.3 Errores uniformes

Todos los errores deben responder con la misma forma, sin filtrar detalles internos:

```json
{"error": "codigo_corto", "mensaje": "Descripción breve", "request_id": "uuid"}
```

Usa los códigos HTTP correctos: **401** sin credenciales o token inválido, **404** recurso
inexistente, **422** parámetros inválidos (FastAPI lo hace solo), **502** cuando falla la
API DataGov, **503** cuando no hay base de datos disponible, **500** para lo inesperado.
Un fallo interno **nunca** debe exponer trazas ni consultas SQL al cliente.

### 7.4 Endpoints de salud

- **`GET /health`** — responde `200` si el proceso está vivo. No consulta nada externo.
- **`GET /ready`** — verifica dependencias (una conexión de prueba a las bases) y responde
  `200` o `503`. Es el que debe usar la plataforma para decidir si enviar tráfico.

Manténlos **sin autenticación**, porque los usan los chequeos automáticos de la
infraestructura.

---

## 8. Fases de implementación

Implementa y **verifica** en este orden. No avances a la siguiente fase sin cerrar la
anterior.

**Fase 1 — Esqueleto.** Proyecto FastAPI que arranca, configuración por variables de
entorno validada, `/health` y `/ready`, logging en JSON, Dockerfile y `docker-compose` con
un PostgreSQL local. *Verificación:* el contenedor levanta y `/health` responde 200.

**Fase 2 — Seguridad.** Autenticación por token bearer aplicada a los endpoints de datos.
*Verificación:* sin token responde 401; con token correcto responde 200; el token no
aparece en los logs.

**Fase 3 — Comentarios de un municipio.** Repositorio de solo lectura, consulta
parametrizada, parseo tolerante del JSON multilingüe y el endpoint
`GET /api/v1/comentarios` contra una sola base. *Verificación:* con datos de prueba, la
paginación por `desde_id` avanza correctamente y no repite ni omite registros.

**Fase 4 — Multi-tenant.** Catálogo de municipios, un pool por municipio, consulta en
paralelo, tolerancia a fallos parciales y el campo `municipios_con_error`.
*Verificación:* apagando una base de prueba, la respuesta sigue devolviendo los demás
municipios y reporta el fallido.

**Fase 5 — Cliente DataGov (mock).** Adaptador con la interfaz definitiva e
implementación simulada, con timeouts y reintentos. *Verificación:* pruebas que simulan
timeout, 500 y respuesta correcta.

**Fase 6 — Republicación para CKAN.** Endpoint `/api/v1/datasets/{id}.{formato}` con CSV,
JSON y GeoJSON, cabeceras correctas y reglas de calidad. *Verificación:* descargar el CSV
y comprobar encabezados únicos, columnas consistentes y UTF-8.

**Fase 7 — Endurecimiento.** Límite de peticiones, caché si aplica, documentación OpenAPI
revisada, README completo y pruebas automatizadas.

---

## 9. Criterios de aceptación

La API se considera terminada cuando:

1. Sin token válido, ningún endpoint de datos entrega información (401).
2. `GET /api/v1/comentarios` devuelve comentarios de los 14 municipios, con el municipio
   identificado en cada registro y las fechas en UTC ISO 8601.
3. El texto de cada comentario llega separado en español e inglés, y las filas antiguas en
   texto plano no rompen la respuesta.
4. La paginación por `desde_id` permite recorrer todo el histórico sin repetir ni perder
   registros.
5. Si una base de datos municipal está caída, la respuesta sigue siendo exitosa para las
   demás y el municipio aparece en `municipios_con_error`.
6. El endpoint de datasets entrega CSV/JSON/GeoJSON con el `Content-Type` correcto y sin
   anomalías de calidad.
7. **Un portal CKAN real logra crear un recurso** apuntando al endpoint de la API. *(Esta
   es la prueba definitiva del flujo de bajada.)*
8. No hay ningún secreto en el repositorio y la aplicación no arranca si falta
   configuración obligatoria.
9. Los logs salen en JSON, sin token ni datos personales, y con identificador de
   correlación.
10. Existen pruebas automatizadas de seguridad, paginación, parseo del comentario y
    tolerancia a fallos.

---

## 10. Pruebas recomendadas

Prioriza estas pruebas automatizadas: petición sin token y con token inválido (401);
parseo del campo `comment` en sus tres variantes (JSON válido, texto plano, JSON
malformado); paginación por cursor con datos de prueba; simulación de una base caída;
simulación de timeout de la API DataGov; y generación de CSV verificando encabezados,
número de columnas y codificación.

Para la prueba de integración final con CKAN: publica la API con un dominio accesible,
crea un recurso en un portal apuntando a `https://<dominio>/api/v1/datasets/<id>.csv`
configurando autenticación **bearer** con el token, y confirma que el recurso se crea y
previsualiza correctamente.

---

## 11. Errores comunes que debes evitar

Escribir `package_Id` sin comillas dobles en SQL (la consulta falla). Paginar con `OFFSET`
en lugar de cursor. Asumir que el campo `comment` es texto plano. Asumir que el `id` es
único entre municipios. Devolver 500 cuando falla un solo municipio en vez de degradar
con elegancia. Exponer la API en una IP privada o en un host `.internal` (CKAN la
bloquearía). Devolver CSV sin `Content-Type` correcto. Registrar el token o el contenido
de los comentarios en los logs. Concatenar parámetros dentro del SQL.

---

## 12. Documentos relacionados

- `CONTEXTO-API-VALLEDATA.md` — **de lectura obligatoria previa**.
- `CONTEXTO-API-DATAGOV.md` — el otro lado de la integración.
- `IMPLEMENTACION-API-DATAGOV.md` — pasos de la API hermana.
- `documentacion/apis_externas.md` — arquitectura aprobada.
