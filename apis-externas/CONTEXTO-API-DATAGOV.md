# CONTEXTO — API DataGov

> **Documento de contexto para asistentes de IA y desarrolladores.**
> Léelo completo antes de escribir una sola línea de código. Contiene el ecosistema,
> el rol exacto de este servicio y las decisiones ya tomadas.
> Documento hermano: `CONTEXTO-API-VALLEDATA.md`. Pasos de construcción:
> `IMPLEMENTACION-API-DATAGOV.md`.

---

## 1. Qué es este proyecto

**API DataGov** es un servicio HTTP nuevo e independiente que actúa como **capa de
integración del proyecto DataGov** frente al proyecto externo **ValleData**. Es un
proyecto autónomo, con repositorio y despliegue propios.

Su razón de existir es doble: por un lado, **evitar que servicios de ValleData accedan
directamente a BigQuery**; por otro, **darle a DataGov el control** sobre qué información
sale hacia afuera y qué información entra para ser procesada.

### 1.1 Sus dos responsabilidades

**Flujo de bajada (Parte 1: DataGov → ValleData).** La API consulta la **capa Gold de
BigQuery** usando una cuenta de servicio con permisos mínimos de lectura, y expone
únicamente la información autorizada mediante un endpoint que consumirá la API ValleData.
Aquí la API DataGov es *servidor*.

```
BigQuery Gold → [API DataGov] → API ValleData → CKAN → recurso publicado
```

**Flujo de subida (Parte 2: ValleData → DataGov).** La API consume el endpoint de
**comentarios** que expone la API ValleData y pone esa información a disposición de los
procesos analíticos de DataGov (los DAGs que ejecutan el análisis de sentimiento y
persisten el resultado en BigQuery). Aquí la API DataGov es *cliente* de ValleData y
*proveedor* para los DAGs.

```
API ValleData → [API DataGov] → DAG (análisis de sentimiento) → BigQuery Gold
```

### 1.2 Lo que esta API NUNCA hace

**No accede a la base de datos PostgreSQL de ValleData** bajo ninguna circunstancia. No
conoce la estructura interna de las tablas de los portales CKAN. Su única dependencia
hacia el otro proyecto es el **contrato HTTP** que expone la API ValleData.

Tampoco expone BigQuery de forma genérica: solo publica los conjuntos de datos
explícitamente autorizados.

---

## 2. El ecosistema DataGov (dónde encaja)

DataGov es un proyecto de datos y analítica en **Google Cloud Platform**, independiente
del proyecto ValleData (son dos proyectos GCP distintos). Sus componentes relevantes para
esta integración son:

- **BigQuery, capa Gold**: el almacén de datos ya procesados, limpios y confiables. Es la
  fuente de la Parte 1.
- **DAGs de analítica** (orquestados con Airflow / Cloud Composer): los procesos que
  transforman y analizan datos. En la Parte 2 son quienes ejecutan el **análisis de
  sentimiento** sobre los comentarios recibidos y escriben el resultado en una tabla Gold.
- **Cuentas de servicio (Service Accounts)**: las identidades técnicas que dan acceso a
  los recursos de GCP, siempre bajo el principio de **mínimo privilegio**.

---

## 3. El otro lado de la integración (qué debes saber de ValleData)

ValleData es una plataforma de datos abiertos basada en **CKAN 2.11**, desplegada en
Kubernetes, compuesta por **14 portales municipales** del Valle del Cauca (Alcalá,
Argelia, Bolívar, Cerrito, El Águila, Guacarí, La Victoria, Pradera, Riofrío, San Pedro,
Trujillo, Ulloa, Vijes y Yotoco) más una instancia federadora.

Para esta API, lo relevante es:

**En la Parte 1**, el consumidor final de los datos es un portal CKAN, que ingiere la
información como un "recurso" a partir de una URL. CKAN solo acepta ciertos formatos
(**JSON, CSV, XLS, XLSX, PDF, GEOJSON, SHP, XML**). Aunque la API DataGov no habla
directamente con CKAN —habla con la API ValleData—, conviene que los datos que expone
sean **fácilmente convertibles a CSV o JSON tabular**, sin estructuras exóticas ni
anidamientos profundos innecesarios.

**En la Parte 2**, la información que llega son **comentarios de ciudadanos** publicados
en los portales. Cada comentario trae su texto (en español e inglés, porque el portal los
traduce automáticamente), el identificador del dataset comentado, el autor, la fecha en
**UTC** y el **municipio** de origen. La API ValleData es multi-tenant, es decir, entrega
en un mismo endpoint los comentarios de los 14 municipios, diferenciados por un campo.

---

## 4. Decisiones ya tomadas (no reabrir sin justificación)

- **Lenguaje y framework:** **Python 3 + FastAPI**. Es coherente con el ecosistema de
  datos (Python es el lenguaje estándar en analítica y en los DAGs de Airflow), tiene
  cliente oficial de BigQuery y genera documentación OpenAPI automáticamente.
- **Despliegue:** **aún no definido** con el equipo de infraestructura. Por eso la API
  debe construirse como un **contenedor Docker portable**, configurable exclusivamente por
  **variables de entorno**, capaz de correr igual en Cloud Run o en GKE.
- **Acceso a BigQuery:** mediante **cuenta de servicio con permisos de solo lectura**
  sobre el dataset o las tablas específicamente autorizadas. Nunca con permisos de
  escritura o administración.
- **Comunicación entre las dos APIs:** puede ir por **red privada** (no aplica la
  restricción anti-SSRF que sí afecta a CKAN, descrita en el contexto de ValleData), pero
  siempre **autenticada**.
- **Superficie mínima:** la API expone solo lo estrictamente necesario para la
  integración. No es una API de propósito general sobre BigQuery.

---

## 5. Principios de diseño que deben respetarse

**Mínimo privilegio.** La identidad que consulta BigQuery solo puede leer, y solo el
dataset autorizado. Si alguien pide "exponer una tabla más", eso implica ampliar
explícitamente los permisos, no dar acceso amplio "por si acaso".

**Lista blanca, no lista negra.** Los conjuntos de datos que se pueden consultar deben
estar declarados explícitamente en configuración. Nunca se debe permitir que el
consumidor envíe una consulta SQL libre ni un nombre de tabla arbitrario: eso abriría la
puerta a inyección SQL y a fuga de información.

**Desacoplamiento.** Si mañana cambia la estructura interna de una tabla en BigQuery, el
ajuste se hace en esta API, sin que ValleData ni CKAN tengan que enterarse. Esa es
precisamente la razón de existir de esta capa.

**Control de costos.** BigQuery cobra por volumen de datos escaneado. Las consultas deben
ser acotadas (columnas específicas, filtros, límites de filas y paginación), y conviene
prever caché para respuestas repetidas.

**Trazabilidad.** Toda solicitud recibida y toda consulta ejecutada debe quedar
registrada, para poder auditar qué información salió, hacia dónde y cuándo.

---

## 6. Puntos pendientes de definir con los equipos

Estos puntos vienen del documento de arquitectura y **siguen abiertos**; si el desarrollo
llega a ellos, hay que consultarlos, no inventarlos:

1. **Qué datasets y tablas concretas** de la capa Gold se exponen en la Parte 1, y con qué
   columnas.
2. **Mecanismo de autenticación entre las dos APIs**: tokens de identidad de GCP entre
   servicios, OAuth 2.0 o llaves gestionadas.
3. **Contrato exacto de la API ValleData** para la Parte 2 (rutas, parámetros de
   paginación, esquema de respuesta) — lo define el equipo de ValleData.
4. **Periodicidad de la recolección** de comentarios y estrategia de reprocesos.
5. **Esquema de la tabla Gold destino** donde se guardarán los comentarios ya analizados,
   incluyendo los campos del resultado del análisis de sentimiento y su particionamiento.
6. **Motor de análisis de sentimiento** que usarán los DAGs (servicio gestionado de GCP,
   modelo propio, u otro).
7. **Cómo consumen los DAGs esta API** (si la llaman directamente o si la API deja los
   datos en un área intermedia).
8. **Configuración de red** entre proyectos (Shared VPC, reglas de firewall, DNS).

---

## 7. Glosario rápido

- **Capa Gold**: en una arquitectura por capas (bronce/plata/oro), es la capa de datos ya
  limpios, integrados y listos para consumo analítico o publicación.
- **BigQuery**: el almacén de datos analítico de Google Cloud.
- **DAG**: un flujo de trabajo programado con dependencias entre tareas (Airflow /
  Cloud Composer).
- **Service Account**: identidad técnica de GCP que usan los servicios para autenticarse
  entre sí, en lugar de credenciales de personas.
- **CKAN**: la plataforma de datos abiertos que usan los portales de ValleData.
- **Análisis de sentimiento**: técnica que clasifica un texto según la emoción o polaridad
  que expresa (positivo, negativo, neutro).

---

## 8. Documentos relacionados

- `CONTEXTO-API-VALLEDATA.md` — el contexto de la API del otro lado (incluye las
  restricciones reales de CKAN y la estructura de los comentarios).
- `IMPLEMENTACION-API-DATAGOV.md` — el paso a paso para construir esta API.
- `documentacion/apis_externas.md` — el documento de arquitectura aprobado (visión general).
