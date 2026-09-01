# CONTEXTO — API ValleData

> **Documento de contexto para asistentes de IA y desarrolladores.**
> Léelo completo antes de escribir una sola línea de código. Contiene el ecosistema,
> las restricciones reales verificadas en el código de CKAN y las decisiones ya tomadas.
> Documento hermano: `CONTEXTO-API-DATAGOV.md`. Pasos de construcción:
> `IMPLEMENTACION-API-VALLEDATA.md`.

---

## 1. Qué es este proyecto

**API ValleData** es un servicio HTTP nuevo e independiente que actúa como **capa de
integración del proyecto ValleData** frente al proyecto externo **DataGov**. Es un
proyecto autónomo (repositorio propio, despliegue propio); **no** es una extensión de
CKAN ni se instala dentro de los portales.

Su razón de existir es que **ningún proyecto acceda directamente a la base de datos del
otro**. ValleData expone y consume información **solo** a través de esta API.

### 1.1 Sus dos responsabilidades

Esta API participa en los dos flujos de interoperabilidad, con un rol distinto en cada uno:

**Flujo de bajada (Parte 1: DataGov → ValleData).** La API consume los datos que la API
DataGov expone desde BigQuery y los **republica en un formato que los portales CKAN puedan
ingerir como recurso**. Aquí la API ValleData es *cliente* de la API DataGov y *servidor*
para CKAN.

```
BigQuery Gold → API DataGov → [API ValleData] → CKAN → se crea el recurso
```

**Flujo de subida (Parte 2: ValleData → DataGov).** La API lee los **comentarios** que los
ciudadanos dejan en los portales CKAN (almacenados en PostgreSQL) y los expone en un
endpoint para que la API DataGov los recoja y los procese analíticamente (análisis de
sentimiento). Aquí la API ValleData es *servidor* para la API DataGov.

```
PostgreSQL (comentarios CKAN) → [API ValleData] → API DataGov → DAG → BigQuery Gold
```

### 1.2 Lo que esta API NUNCA hace

No consulta BigQuery ni tiene credenciales de DataGov. No conoce la estructura interna
de las tablas de DataGov. Su única dependencia hacia el otro proyecto es el **contrato
HTTP** que expone la API DataGov.

---

## 2. El ecosistema ValleData (dónde encaja)

ValleData es una plataforma de datos abiertos basada en **CKAN 2.11** desplegada en
**Google Kubernetes Engine (GKE)**, compuesta por **15 instancias independientes**:

- **14 portales municipales** del Valle del Cauca: Alcalá, Argelia, Bolívar, Cerrito,
  El Águila, Guacarí, La Victoria, Pradera, Riofrío, San Pedro, Trujillo, Ulloa, Vijes
  y Yotoco.
- **1 instancia "harvest"** (federadora) que cosecha los datasets de los municipios.

Cada instancia tiene su **propia imagen Docker, su propio subdominio y su propia base de
datos PostgreSQL**. Esto es fundamental: **no hay una base de datos única**; hay una por
municipio (`ckan_alcala`, `ckan_cerrito`, etc.). El código fuente de las extensiones vive
en el repositorio `datosabiertos-ckan` y los manifiestos de Kubernetes en el repositorio
gemelo `datosabiertos-devops`.

---

## 3. Restricciones REALES del lado CKAN (verificadas en el código)

> Esta sección es la más importante del documento. Son hechos verificados leyendo el
> código de la extensión `ckanext-ckanplugin`, no supuestos. Ignorarlos hace que la
> integración falle.

### 3.1 CKAN ya sabe consumir endpoints externos (funcionalidad RF-001)

Los portales tienen una funcionalidad llamada **RF-001** que permite al administrador
crear un recurso **a partir de una URL o endpoint HTTP** en lugar de subir un archivo.
La API ValleData se apoyará en esta funcionalidad existente: **no hay que desarrollar
nada nuevo dentro de CKAN** para el flujo de bajada.

### 3.2 Formatos que CKAN acepta

CKAN solo admite estos formatos (lista blanca en el código, constante
`RF001_ALLOWED_FORMATS`):

**JSON, CSV, XLS, XLSX, PDF, GEOJSON, SHP, XML.**

Cualquier otra cosa se rechaza. Para una API de datos, los formatos naturales son
**CSV, JSON y GEOJSON**.

### 3.3 Cómo detecta CKAN el formato (importante para diseñar las respuestas)

CKAN determina el formato del recurso en este orden: primero por la **extensión de la
URL**, luego por el **`Content-Type`** de la respuesta y, si no logra determinarlo, hace
*sniffing* del contenido. Los `Content-Type` que reconoce explícitamente son
`application/json`, `text/json`, `application/geo+json`, `text/csv` y `application/csv`.

**Consecuencia de diseño:** la API ValleData debe devolver un `Content-Type` correcto y,
preferiblemente, exponer rutas cuya URL termine en la extensión esperada (por ejemplo
`/datasets/ventas.csv`), para que CKAN clasifique el recurso sin ambigüedad.

### 3.4 Autenticación que CKAN puede usar al consumir un endpoint

CKAN soporta exactamente estos modos al llamar a un endpoint externo (constante
`AUTH_TYPES`): **`none`, `bearer`, `api_key` y `basic`**.

**Consecuencia de diseño:** la autenticación de la API ValleData hacia CKAN **debe** ser
uno de esos cuatro. Lo recomendado es **`bearer`** (token en la cabecera
`Authorization`). No sirven mecanismos que CKAN no implementa (por ejemplo, firmas
personalizadas o mTLS) para este flujo.

### 3.5 ⚠️ CKAN BLOQUEA redes privadas (protección anti-SSRF) — hallazgo crítico

El código valida el destino antes de llamar a una URL y **rechaza**:

- Direcciones IP **privadas** (`10.x.x.x`, `192.168.x.x`, `172.16-31.x.x`), de *loopback*,
  *link-local*, *multicast* y reservadas.
- La IP de metadatos de la nube (`169.254.169.254`).
- Los hosts `localhost` y cualquier host terminado en **`.local`** o **`.internal`**.

Si la validación falla, devuelve el error `blocked` y **no realiza la petición**.

**Implicación directa:** el diseño original planteaba comunicación por **red privada
(Shared VPC)**. Tal como está el código hoy, **si la API ValleData se expone en una IP
privada o en un host interno del clúster, CKAN la rechazará**.

**Decisión tomada:** la API ValleData se expondrá con un **hostname público con HTTPS,
protegido por autenticación** (token). Así CKAN puede consumirla sin modificar su
protección anti-SSRF. La seguridad se garantiza por credenciales y TLS, no por
oscuridad de red.

> Nota: la comunicación **entre las dos APIs** (ValleData ↔ DataGov) sí puede ir por red
> privada, porque esa protección solo aplica a lo que consume CKAN.

### 3.6 Límite de peticiones en CKAN

CKAN aplica un límite de **20 peticiones por 60 segundos por usuario** al previsualizar
endpoints. No afecta el diseño de la API, pero explica por qué una prueba muy repetitiva
puede empezar a fallar temporalmente.

---

## 4. Los comentarios de CKAN (fuente de datos de la Parte 2)

> Estructura verificada directamente en la base de datos y en el modelo del plugin.

### 4.1 La tabla `comments`

Cada portal municipal guarda los comentarios en una tabla llamada `comments` dentro de su
propia base de datos. Sus columnas son:

- **`id`** — entero autoincremental, llave primaria. **Es el mejor campo para paginación
  incremental** (ver 4.4).
- **`package_Id`** — texto; el identificador (UUID) del dataset comentado. Tiene llave
  foránea contra la tabla `package` de CKAN con borrado en cascada. *(Ojo: el nombre de la
  columna lleva mayúscula en la "I", por lo que en SQL debe escribirse entre comillas
  dobles: `"package_Id"`.)*
- **`comment`** — texto. **No es texto plano: contiene un JSON serializado** (ver 4.2).
- **`user_id`** — texto de hasta 100 caracteres; identifica al autor del comentario.
- **`created`** — marca de tiempo **sin zona horaria, almacenada en UTC**, con valor por
  defecto `now()`.

### 4.2 El campo `comment` es un JSON multilingüe

El portal traduce automáticamente cada comentario y lo guarda serializado así:

```json
{"en": "Good dataset", "es": "Buen conjunto de datos"}
```

**Consecuencia de diseño:** la API **debe parsear ese JSON** y exponer los dos idiomas de
forma estructurada. Debe además ser tolerante: si alguna fila antigua contiene texto plano
(no JSON), no debe romperse, sino tratarla como el texto original.

### 4.3 Sí hay varios comentarios por dataset

Aunque el modelo declara una restricción de unicidad por dataset, **la base de datos real
no la tiene aplicada**: existen datasets con múltiples comentarios (se verificó uno con
11). La API debe asumir **relación uno-a-muchos** entre dataset y comentarios.

### 4.4 Zona horaria y estrategia de extracción incremental

Los comentarios se **almacenan en UTC** (la conversión a hora Colombia se hace solo al
mostrarlos en el portal). La API debe exponer las fechas en **UTC en formato ISO 8601**,
dejando cualquier conversión al consumidor.

Para la carga incremental hacia DataGov, la recomendación es usar **`id` como cursor**
(`WHERE id > último_id_procesado ORDER BY id`), porque es estrictamente creciente y no
depende de relojes ni de zonas horarias. La fecha `created` sirve como filtro adicional,
pero no como cursor principal.

### 4.5 Multi-tenant: 14 bases de datos

**Decisión tomada:** una **sola API multi-tenant** que se conecta a las bases de los 14
municipios y expone los comentarios de todos, **identificando el municipio en cada
registro**. No se despliega una API por municipio.

Esto implica que la API necesita: un catálogo de municipios con su cadena de conexión, un
manejo de conexiones eficiente (pool por municipio), y **tolerancia a fallos parciales**
(si un municipio no responde, los demás deben seguir funcionando y el error debe quedar
reportado).

---

## 5. Decisiones ya tomadas (no reabrir sin justificación)

- **Lenguaje y framework:** **Python 3 + FastAPI**. Es el mismo lenguaje del resto del
  proyecto (CKAN y sus extensiones son Python), da documentación OpenAPI automática y
  validación de datos con Pydantic.
- **Despliegue:** **aún no definido** con DevOps. Por eso la API debe construirse como un
  **contenedor Docker portable**, sin dependencias del entorno, configurable por
  **variables de entorno**. Debe poder correr igual en Cloud Run o en GKE.
- **Exposición hacia CKAN:** **hostname público con HTTPS + autenticación por token**
  (por la restricción del punto 3.5).
- **Alcance de comentarios:** **multi-tenant** (los 14 municipios).
- **Base de datos:** la API **solo lee** de PostgreSQL. Nunca escribe en las bases de los
  portales.

---

## 6. Puntos pendientes de definir con los equipos

Estos puntos vienen del documento de arquitectura y **siguen abiertos**; si el desarrollo
llega a ellos, hay que consultarlos, no inventarlos:

1. **Contrato con la API DataGov** (Parte 1): rutas exactas, parámetros, esquema de
   respuesta y versionado que expondrá DataGov.
2. **Mecanismo de autenticación entre las dos APIs** (distinto del de CKAN): tokens de
   identidad de GCP entre servicios, OAuth 2.0, o llaves.
3. **Alcance de los datos**: qué conjuntos concretos de la capa Gold se exponen (Parte 1)
   y qué columnas/filtros de comentarios se envían (Parte 2).
4. **Periodicidad y estrategia de carga** de la Parte 2 (cada cuánto consulta DataGov,
   manejo de reprocesos e idempotencia).
5. **Credenciales de acceso** a las 14 bases PostgreSQL (usuario de solo lectura) —
   deben ser gestionadas por DevOps vía Secret Manager.
6. **Dominio público** que se asignará a la API y su certificado.

---

## 7. Glosario rápido

- **CKAN**: la plataforma de datos abiertos sobre la que están hechos los portales.
- **Dataset / conjunto de datos**: la ficha de información publicada (`package` en la
  base de datos).
- **Recurso**: el archivo o endpoint concreto que pertenece a un dataset (el CSV, el
  JSON, etc.).
- **RF-001**: la funcionalidad del portal que permite crear recursos desde una URL/endpoint
  externo, con validación de formato y protecciones de seguridad.
- **Capa Gold**: la capa de datos ya procesados y confiables dentro de BigQuery en DataGov.
- **DAG**: un flujo de trabajo programado (Airflow/Composer) en DataGov que procesa datos.
- **Multi-tenant**: un solo servicio que atiende a varios municipios diferenciándolos
  internamente.

---

## 8. Documentos relacionados

- `CONTEXTO-API-DATAGOV.md` — el contexto de la API del otro lado.
- `IMPLEMENTACION-API-VALLEDATA.md` — el paso a paso para construir esta API.
- `documentacion/apis_externas.md` — el documento de arquitectura aprobado (visión general).
- `documentacion/listado_endpoints.md` — inventario de endpoints existentes en los portales.
