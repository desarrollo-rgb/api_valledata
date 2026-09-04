# Manejo de errores — API ValleData

Guía para diagnosticar fallos: **qué responde** la API ante cada error y **qué se registra
en el log**, para distinguir rápido si el problema es del que consume (mal uso), de una
dependencia externa, o del código.

---

## ¿Dónde veo por qué falló?

La API escribe cada error en la **consola (`stdout`)**. Según dónde corra:

- **Local:** en la terminal donde tienes `uvicorn`.
- **Producción (Cloud Run / GKE):** GCP lo captura automáticamente en **Cloud Logging**.

Consultar en producción:

```bash
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=valledata" --limit 50
```

O desde la consola de GCP: **Logging → Logs Explorer**, filtrando por el servicio.

---

## Cómo leer el código de estado

| Código | De quién es el problema |
| --- | --- |
| **4xx** 🟡 | Del que llama: token, parámetros o ruta. **No es el código de la API.** |
| **502 / 503** 🔵 | Una dependencia externa (DataGov, PostgreSQL) o la infraestructura. |
| **500** 🔴 | El código o la configuración. El log trae el **stack trace completo**. |

Además, uvicorn escribe una línea por cada petición con su código, por ejemplo:

```
INFO:  10.0.0.5 - "GET /api/v1/bd_ckan/comments HTTP/1.1" 200
```

---

## Tabla de fallos

| # | Escenario | HTTP | Cuerpo (`detail`) | Qué verás en el log | Categoría |
|---|---|---|---|---|---|
| 1 | Llamada sin token | **401** | `"No autorizado"` | Línea de acceso `... 401` | 🟡 Mal consumo |
| 2 | Token equivocado | **401** | `"No autorizado"` | Línea de acceso `... 401` | 🟡 Mal consumo |
| 3 | `?limite=0` (o > 1000) en cultivos | **422** | detalle de validación | Línea de acceso `... 422` | 🟡 Mal consumo |
| 4 | Ruta que no existe | **404** | `"Not Found"` | Línea de acceso `... 404` | 🟡 Mal consumo |
| 5 | 1 municipio de PostgreSQL falla | **200** | `municipios_con_error: ["ulloa"]` | `WARNING: No se pudieron leer los comentarios de ulloa: connection timeout` | 🔵 Dependencia/infra |
| 6 | Túnel caído / servidor inaccesible (fallan las 14) | **200** | `total: 0`, `municipios_con_error: [14 nombres]` | 14 líneas `WARNING: No se pudieron leer los comentarios de ...: server closed the connection` | 🔵 Infra |
| 7 | DataGov caído (al pedir cultivos) | **502** | `"No se pudo contactar a la API DataGov. Intenta más tarde."` | `WARNING: DataGov no disponible: [Errno 111] Connection refused` | 🔵 Dependencia |
| 8 | DataGov responde con error (p. ej. 500) | **502** | `"La API DataGov respondió con un error."` | `WARNING: DataGov respondio con error: codigo 500` | 🔵 Dependencia |
| 9 | `DATAGOV_API_TOKEN` no coincide con el de DataGov | **502** | `"La API DataGov respondió con un error."` | `WARNING: DataGov respondio con error: codigo 401` | 🟡 Mala config |
| 10 | `/ready` con PostgreSQL caído (p. ej. túnel apagado) | **503** | `"not ready"` | `WARNING: Readiness: PostgreSQL no responde: ...` | 🔵 Infra |
| 11 | Excepción no prevista (bug real) | **500** | `"Error interno del servidor."` | `ERROR` + **stack trace completo** | 🔴 Bug de código |

---

## Principios de diseño

- **Al consumidor nunca se le expone el detalle técnico:** los mensajes son genéricos. El
  detalle (motivo, stack trace) va solo al log.
- **Un fallo de una dependencia no se disfraza de éxito:** si DataGov falla, respondemos
  `502`, no un `200` vacío.
- **Fallos parciales de datos se informan, no se ocultan:** si una base de un municipio no
  responde, sus comentarios no vienen, pero los demás sí, y su nombre aparece en
  `municipios_con_error`. El motivo exacto queda en el log.
- **Nunca se escribe en las bases:** el acceso a PostgreSQL es de solo lectura.
