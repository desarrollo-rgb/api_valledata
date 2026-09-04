# Variables de entorno — API ValleData

Referencia de todas las variables del archivo `.env` para un despliegue **real** (no el
modo de desarrollo). Pensada para quien configura y despliega el servicio.

> **Reglas de oro**
> - El `.env` real **nunca** se sube a git. En producción (Cloud Run / GKE) estas variables
>   se cargan como variables de entorno de la plataforma, y los **secretos** desde
>   **Secret Manager**.
> - Los valores marcados como **🔒 Secreto** no deben quedar en texto plano en el repo ni
>   en logs.

---

## Seguridad

| Variable | Qué hace | Obligatoria | 🔒 | Valor real a usar |
| --- | --- | :---: | :---: | --- |
| `API_TOKEN` | Token que ValleData **exige** a quien lo consume (la API DataGov). Se valida en la cabecera `Authorization: Bearer <token>`. | **Sí** (si falta, la app no arranca) | 🔒 | Un token largo y aleatorio. Generar con `openssl rand -hex 32`. Debe entregarse a DataGov. |

---

## Flujo 1 — cliente hacia la API DataGov (cultivos)

| Variable | Qué hace | Obligatoria | 🔒 | Valor real a usar |
| --- | --- | :---: | :---: | --- |
| `USAR_DATAGOV_FALSO` | Interruptor de modo. `true` = datos de ejemplo; `false` = llama a DataGov por HTTP. | Sí | | `false` |
| `DATAGOV_API_BASE_URL` | URL base de la API DataGov. | Sí | | URL del servicio DataGov desplegado (p. ej. `https://datagov....run.app`). En local: `http://localhost:8000`. |
| `DATAGOV_API_TOKEN` | Token que ValleData **presenta** a DataGov al consumirla. | Sí | 🔒 | Debe ser **idéntico** al `API_TOKEN` configurado en DataGov. |
| `DATAGOV_TIMEOUT_SEGUNDOS` | Segundos máximo de espera por respuesta de DataGov. | No (por defecto 30) | | `30` |

---

## Flujo 2 — PostgreSQL (comentarios de los portales CKAN)

| Variable | Qué hace | Obligatoria | 🔒 | Valor real a usar |
| --- | --- | :---: | :---: | --- |
| `USAR_POSTGRES_FALSO` | Interruptor de modo. `true` = comentarios de ejemplo; `false` = se conecta a las 14 bases reales. | Sí | | `false` |
| `POSTGRES_HOST` | Host del servidor PostgreSQL (Cloud SQL). | Sí | | En producción (dentro de la VPC): la **IP privada** del Cloud SQL (p. ej. `10.146.0.3`). En local: `127.0.0.1` (a través del túnel). |
| `POSTGRES_PORT` | Puerto del servidor. | Sí | | `5432` |
| `POSTGRES_USER` | Usuario de la base de datos. Debe ser de **solo lectura**. | Sí | 🔒 | Usuario readonly entregado por el equipo. |
| `POSTGRES_PASSWORD` | Contraseña del usuario. | Sí | 🔒 | La contraseña de ese usuario (desde Secret Manager). |

**Notas de PostgreSQL:**
- Son **14 bases** (una por municipio) dentro de **una misma instancia**. El servicio se
  conecta al mismo host/puerto/usuario y solo cambia el `dbname`. La lista de bases está en
  `app/config.py` (`postgres_databases`), no en el `.env`.
- El acceso es **solo lectura** y cada conexión se marca `read_only`: nunca se escribe en
  los portales.
- En **local**, el host es `127.0.0.1` porque la instancia es privada y se llega por un
  túnel (ver la sección §4.2 del `README.md`). En **producción**, al correr dentro de la
  VPC, se usa la IP privada directamente.

---

## Coincidencia de tokens entre servicios

ValleData participa en dos relaciones de autenticación. Estas igualdades **deben cumplirse**:

| Este valor… | …debe ser igual a… | Porque |
| --- | --- | --- |
| `ValleData.API_TOKEN` | `DataGov.VALLEDATA_API_TOKEN` | DataGov consume el endpoint de comentarios de ValleData (Flujo 2). |
| `ValleData.DATAGOV_API_TOKEN` | `DataGov.API_TOKEN` | ValleData consume el endpoint de cultivos de DataGov (Flujo 1). |

Si alguna no coincide, el consumidor recibe `401` y el endpoint que depende de ese llamado
responde `502`.

---

## Ejemplo de `.env` real (con secretos como marcadores)

```dotenv
# Seguridad
API_TOKEN=<secreto: openssl rand -hex 32>

# Flujo 1 — cliente hacia DataGov
USAR_DATAGOV_FALSO=false
DATAGOV_API_BASE_URL=https://<host-de-datagov>
DATAGOV_API_TOKEN=<secreto: igual al API_TOKEN de DataGov>
DATAGOV_TIMEOUT_SEGUNDOS=30

# Flujo 2 — PostgreSQL (14 portales CKAN)
USAR_POSTGRES_FALSO=false
POSTGRES_HOST=10.146.0.3
POSTGRES_PORT=5432
POSTGRES_USER=<usuario readonly>
POSTGRES_PASSWORD=<secreto>
```
