# Contrato de APIs — Comentarios

Documento de referencia del endpoint de **comentarios**, que existe en las dos APIs del
proyecto. Describe qué devuelve, la diferencia entre **expose** y **consume**, el parámetro
que admite y los errores posibles.

> **Qué son los comentarios:** opiniones que hacen los ciudadanos sobre los recursos de los
> conjuntos de datos publicados en los **14 portales CKAN** (uno por municipio). ValleData
> los lee de las bases de esos portales; DataGov los pide a ValleData para que el DAG de
> analítica los procese.

> ⚠️ **Estado del despliegue (importante):** la API **DataGov aún no está desplegada**. Por
> ahora, para obtener los comentarios **se usa el endpoint de ValleData** (`expose`). Cuando
> DataGov esté arriba, su endpoint (`consume`) responderá **exactamente igual**: el mismo
> parámetro, la misma estructura de respuesta y los mismos campos — porque DataGov solo
> reexpone lo que le entrega ValleData, sin transformarlo. Es decir, el consumidor podrá
> cambiar de uno a otro sin tocar la forma de leer la respuesta.

---

## expose vs consume: quién los expone y quién los consume

El mismo recurso (`bd_ckan/comments`) aparece en las dos APIs, pero con un rol distinto según
de dónde **nace** el dato:

| API | Endpoint | Rol | De dónde salen los comentarios |
| --- | --- | --- | --- |
| **ValleData** | `GET /api/v1/expose/bd_ckan/comments` | **expose** | Fuente **propia**: los lee de las 14 bases PostgreSQL de CKAN. |
| **DataGov** | `GET /api/v1/consume/bd_ckan/comments` | **consume** | Los pide a **ValleData** por HTTP y los reexpone tal cual. |

- **expose** = el dato nace en la fuente propia de esa API (aquí, las bases CKAN de ValleData).
- **consume** = el dato viene de la **otra** API (DataGov no tiene comentarios propios: los
  consume de ValleData).

El flujo completo cuando el DAG pide comentarios:

```
DAG ──> [DataGov] GET /consume/bd_ckan/comments ──> [ValleData] GET /expose/bd_ckan/comments ──> 14 bases PostgreSQL (CKAN)
```

DataGov **no transforma** la respuesta: entrega el mismo JSON que le dio ValleData.

---

## URLs base

| Entorno | ValleData (expose) | DataGov (consume) |
| --- | --- | --- |
| Local | `http://localhost:8001` | `http://localhost:8000` |
| Producción | `https://api-valledata.valledelcauca.gov.co` | *(aún no desplegada)* |

> Mientras DataGov no esté desplegada, **usa ValleData**. El endpoint de DataGov se
> documenta aquí para que quede listo: responderá igual en cuanto esté disponible.

---

## Autenticación

El endpoint está protegido: para usarlo debes enviar un **token**.

**La regla es simple: solo necesitas el token de la API que estás llamando.**

- ¿Llamas a **ValleData**? → usa el **token de ValleData**.
- ¿Llamas a **DataGov**? → usa el **token de DataGov**.

El token se envía en la cabecera `Authorization`, con la palabra `Bearer` adelante:

```
Authorization: Bearer <token-de-la-api-que-llamas>
```

Si el token falta o es incorrecto, la respuesta es **401** `{"detail": "No autorizado"}`.

> **¿Y el token entre DataGov y ValleData?** No te preocupes por él. Cuando llamas a DataGov,
> DataGov necesita a su vez un token para pedirle los comentarios a ValleData, **pero ese
> token ya está configurado por dentro** (en las variables de entorno del servicio). Tú, como
> consumidor, **nunca lo manejas**: solo pones el token de DataGov y DataGov se encarga del
> resto.

---

## Pruébalo desde el navegador (Swagger)

Cada API trae una interfaz **Swagger** para probar el endpoint sin escribir código, desde el
navegador:

| API | URL de Swagger |
| --- | --- |
| ValleData | `https://api-valledata.valledelcauca.gov.co/docs` |
| DataGov | *(cuando esté desplegada)* `https://<host-datagov>/docs` |

Pasos:

1. Abre la URL de Swagger de la API que quieras probar.
2. Haz clic en el botón **Authorize** (arriba a la derecha) y pega el **token de esa API**
   (según la regla de arriba). Confirma.
3. Busca el endpoint de comentarios, despliégalo y haz clic en **Try it out**.
4. (Opcional) Escribe el parámetro `desde`. Si lo dejas vacío, trae todos.
5. Haz clic en **Execute**. Verás abajo la respuesta real, con su código de estado y el JSON.

> Si no haces el paso 2 (Authorize), el endpoint responderá **401**.

---

## Parámetro: `desde`

Es el único parámetro del endpoint. Sirve para traer solo los comentarios **creados desde una
fecha en adelante** (`created >= desde`).

| Parámetro | Tipo | Obligatorio | Descripción |
| --- | --- | --- | --- |
| `desde` | string (ISO 8601) | No | Fecha, o fecha y hora, desde la cual traer comentarios. **Vacío = todos.** |

| Petición | Resultado |
| --- | --- |
| **sin `desde`** (o `?desde=`) | Todos los comentarios |
| `?desde=2026-07-29` | Desde ese día (00:00) en adelante |
| `?desde=2026-07-29T23:58:33Z` | Desde esa fecha y hora exacta |
| `?desde=<formato inválido>` | **422** |

Notas:
- Acepta **ISO 8601**: fecha sola (`2026-07-29`) o fecha y hora (`2026-07-29T23:58:33Z`, con o
  sin zona).
- En **ValleData** el filtro se empuja a PostgreSQL (`WHERE created >= %s`, parametrizado — sin
  riesgo de inyección) y se aplica por igual a las 14 bases.
- En **DataGov** el parámetro se **valida** (responde 422 si es inválido, sin molestar a
  ValleData) y se **reenvía** tal cual a ValleData, que hace el filtrado real.

---

## Respuesta

Misma forma en las dos APIs (DataGov entrega lo mismo que ValleData).

```json
{
  "comentarios": [
    {
      "id": 1,
      "municipio": "alcala",
      "dataset_id": "9de6140a-3832-46b6-a081-0d05c9acf366",
      "nombre_dataset": "Cultivos del Valle 2026",
      "usuario": "ana",
      "texto_es": "Buen conjunto de datos",
      "texto_en": "Good dataset",
      "fecha": "2026-08-20T10:00:00Z"
    }
  ],
  "total": 1,
  "municipios_con_error": []
}
```

### Campos del nivel superior

| Campo | Tipo | Descripción |
| --- | --- | --- |
| `comentarios` | lista | Los comentarios encontrados. |
| `total` | int | Cantidad de comentarios en `comentarios`. |
| `municipios_con_error` | lista de string | Municipios cuya base **no respondió**. Sus comentarios no vienen, pero los de los demás sí. Lista vacía = todos respondieron. |

### Campos de cada comentario

| Campo | Tipo | Descripción |
| --- | --- | --- |
| `id` | int | Id del comentario **dentro de su municipio**. **No es único entre municipios**: la clave real es `municipio + id`. |
| `municipio` | string | Municipio de origen (derivado de la base: `ckan_alcala` → `alcala`). |
| `dataset_id` | string | Id del dataset comentado (columna `"package_Id"` en CKAN). |
| `nombre_dataset` | string \| null | Nombre legible del dataset (`title` en CKAN). `null` si el dataset no se encontró. |
| `usuario` | string \| null | Autor del comentario. **`null` en comentarios anónimos** (CKAN lo permite). |
| `texto_es` | string \| null | Texto del comentario en español. |
| `texto_en` | string \| null | Texto del comentario en inglés. |
| `fecha` | string | Fecha de creación en UTC, ISO 8601. |

> El texto llega separado por idioma porque en CKAN la columna del comentario es un JSON
> multilingüe `{"es": "...", "en": "..."}`.

---

## Ejemplos de petición

**ValleData (expose) — fuente propia:**
```bash
curl -X GET 'https://api-valledata.valledelcauca.gov.co/api/v1/expose/bd_ckan/comments?desde=2026-07-29' \
  -H 'Authorization: Bearer <token-valledata>'
```

**DataGov (consume) — reexpone lo de ValleData:**
```bash
curl -X GET 'http://localhost:8000/api/v1/consume/bd_ckan/comments?desde=2026-07-29' \
  -H 'Authorization: Bearer <token-datagov>'
```

---

## Errores

Principio general: **al consumidor nunca se le expone el detalle técnico.** Los mensajes son
genéricos; la causa real (motivo, *stack trace*) queda en el **log** del servicio.

### Comunes a ambas APIs

| Código | Cuándo | Cuerpo (`detail`) |
| --- | --- | --- |
| **200** con `municipios_con_error` no vacío | Fallo **parcial**: una o varias bases no respondieron, pero otras sí. **No es un error**: los datos vienen incompletos y se avisa cuáles faltan. | — (respuesta normal) |
| **401** | Token ausente o incorrecto. | `"No autorizado"` |
| **422** | `desde` con formato inválido. | `"Parametro 'desde' invalido..."` |
| **404** | Ruta inexistente. | `"Not Found"` |
| **500** | Error no previsto (bug). El detalle va solo al log. | `"Error interno del servidor."` |

### Específicos de ValleData (expose)

| Código | Cuándo | Cuerpo (`detail`) |
| --- | --- | --- |
| **502** | Fallan **las 14** bases PostgreSQL (la fuente está caída: túnel/VPC abajo, servidor inaccesible). No se devuelve un 200 vacío. | `"No se pudieron leer los comentarios. Intenta más tarde."` |

### Específicos de DataGov (consume)

| Código | Cuándo | Cuerpo (`detail`) |
| --- | --- | --- |
| **502** | No se pudo **contactar** a ValleData (caído, timeout, red). | `"No se pudo contactar a la API ValleData. Intenta más tarde."` |
| **502** | ValleData **respondió con error** (p. ej. token cruzado que no coincide → 401 interno, o fallo interno de ValleData). | `"La API ValleData respondió con un error."` |

> **Cómo distinguir de quién es el problema:**
> - **4xx** → del que llama (token, parámetro, ruta).
> - **502** → una dependencia externa (ValleData, o las bases PostgreSQL).
> - **500** → bug del código; el log trae el *stack trace* completo.
