# Guía de desarrollo — API ValleData (para empezar desde cero)

Esta guía es para alguien que **nunca ha tocado el repo**. Explica cómo clonarlo, correrlo
y cómo **agregar un endpoint nuevo** paso a paso. No asume experiencia previa con el
proyecto.

> ¿Qué hace esta API? Dos cosas: (1) **lee los comentarios** de las 14 bases PostgreSQL de
> los portales CKAN y los **expone**, y (2) **consume** de la API DataGov las vistas de
> analítica de comentarios y las **reexpone**. Si no lo tienes claro, lee el `README.md`.

---

## 1. Requisitos (se instalan una sola vez)

| Herramienta | Para qué | Cómo comprobar |
| --- | --- | --- |
| **pyenv** | Fija la versión de Python del proyecto (3.11.9) | `pyenv --version` |
| **Poetry** | Instala dependencias y crea el entorno virtual | `poetry --version` |
| **git** | Clonar el repo | `git --version` |

> Instalación en Windows (PowerShell): pyenv-win y Poetry tienen instaladores oficiales.
> Tras instalar cada uno, **cierra y abre la terminal** para que el PATH se actualice.

---

## 2. Clonar y dejar el proyecto corriendo

```bash
# 1) Clonar el repo
git clone https://github.com/desarrollo-rgb/api_valledata.git
cd api_valledata

# 2) Usar la version de Python del proyecto (la fija el archivo .python-version)
pyenv install 3.11.9   # solo si no la tienes
pyenv local 3.11.9

# 3) Instalar dependencias (crea el entorno virtual)
poetry install

# 4) Crear tu archivo de configuracion a partir de la plantilla
cp .env.example .env
# Abre .env y pon al menos:  API_TOKEN=cualquier-cosa
# Deja USAR_DATAGOV_FALSO=true y USAR_POSTGRES_FALSO=true para arrancar con datos de
# ejemplo, sin necesidad de DataGov ni de las bases PostgreSQL.

# 5) Levantar el servidor (usa el puerto 8001 para no chocar con DataGov en el 8000)
poetry run uvicorn app.main:app --reload --port 8001
```

Abre **http://localhost:8001/docs** → es Swagger. Dale a **Authorize** 🔒, pega tu
`API_TOKEN`, y prueba los endpoints.

Para correr las pruebas:
```bash
poetry run pytest
```

---

## 3. Cómo está organizado (lo mínimo que debes saber)

```
app/
├── main.py            # arranca FastAPI y "enchufa" los routers
├── config.py          # TODAS las variables de entorno (clase Settings)
├── security.py        # el guardian: valida el token (no lo tocas casi nunca)
├── errors.py          # traduce errores a respuestas HTTP limpias (502, 500, ...)
├── models/
│   └── schemas.py     # el modelo Comentario (contrato de los comentarios CKAN)
├── api/
│   ├── datasets.py    # endpoints que CONSUMEN las vistas de DataGov  <-- caso A
│   └── comentarios.py # endpoint que EXPONE los comentarios de PostgreSQL  <-- caso B
└── services/
    ├── datagov_client.py    # cliente HTTP hacia DataGov (Falso <-> HTTP real)
    └── comentarios_repo.py  # lee las 14 bases PostgreSQL (Falso <-> Postgres real)
```

**La idea clave (patrón que se repite):** cada "fuente de datos" tiene *una interfaz y dos
implementaciones*: una **Falsa** (datos de ejemplo, para desarrollar sin red) y una **real**.
Lo decide una variable de entorno (`USAR_DATAGOV_FALSO`, `USAR_POSTGRES_FALSO`). Por eso
puedes desarrollar y probar sin DataGov ni PostgreSQL.

Hay **dos tipos** de endpoint que podrías agregar. Elige según de dónde venga el dato:

---

## 4. Caso A — Endpoint que CONSUME de DataGov (lo más común)

Es un *pass-through*: ValleData le pide algo a DataGov y devuelve el mismo JSON. Es el caso
de las vistas de comentarios. Supongamos una vista nueva en DataGov: `mi_vista_nueva`.

### Paso 1 — Agregar el endpoint

En `app/api/datasets.py`, copia el patrón de un endpoint existente:

```python
@router.get(
    "/mi_vista_nueva",
    summary="Obtener mi vista nueva",
)
async def obtener_mi_vista_nueva(
    limite: int | None = _LIMITE,
    cliente: ClienteDataGov = Depends(get_cliente_datagov),
) -> dict:
    """Describe que devuelve. ValleData lo obtiene de DataGov."""
    return cliente.obtener_dataset("gold_valledata", "mi_vista_nueva", limite=limite)
```

- `obtener_dataset(fuente, tabla, limite, filtros=None)` arma la URL de DataGov:
  `/api/v1/expose/<fuente>/<tabla>`. Para las vistas de comentarios, `fuente` es
  `gold_valledata`.
- El `router` ya existe con prefijo `/api/v1/consume/gold_valledata` y ya exige token, así
  que tu endpoint quedará en `GET /api/v1/consume/gold_valledata/mi_vista_nueva`.
- ¿Tu endpoint recibe filtros extra (fecha, municipio...)? Míralo en
  `valledata_api_comentarios_detalle`: valida los parámetros y los pasa en `filtros={...}`,
  que el cliente reenvía a DataGov.

### Paso 2 — Agregar datos de ejemplo (modo falso)

En `app/services/datagov_client.py`, dentro de `ClienteDataGovFalso._EJEMPLOS_POR_TABLA`,
agrega una entrada con el nombre de tu vista y un par de filas representativas:

```python
"mi_vista_nueva": [
    {"columna_a": "valor", "columna_b": 123},
    {"columna_a": "otro",  "columna_b": 456},
],
```

### Paso 3 — Probar

Agrega/ajusta una prueba en `tests/test_datasets.py` (guíate por `VISTAS`) y corre:
```bash
poetry run pytest
```
Verifica en Swagger (`/docs`) que responde.

> **Nota:** la URL en ValleData usa el **nombre del dataset de DataGov** (`gold_valledata`).
> Si la vista viviera en otro dataset, se crea un router nuevo con ese prefijo (como se hizo
> con `gold_valledata`) y se registra en `main.py`.

---

## 5. Caso B — Endpoint que EXPONE datos propios desde PostgreSQL (avanzado)

Es el caso del endpoint de comentarios (`/api/v1/expose/bd_ckan/comments`), que lee las 14
bases. Si necesitas exponer otra lectura de PostgreSQL:

1. **El modelo** (opcional): si la forma de la respuesta es nueva, agrégala en
   `app/models/schemas.py` (como `Comentario`).
2. **El repositorio**: en `app/services/` crea un repo con el patrón *Protocol + Falso +
   Postgres*, copiando de `comentarios_repo.py`. Puntos clave de ese archivo:
   - Recorre las 14 bases (`settings.postgres_databases`), una por una.
   - Marca la conexión como **solo lectura** (`conexion.read_only = True`): nunca escribe.
   - Los valores del usuario van **parametrizados** (`WHERE ... >= %s`), nunca pegados al SQL.
   - **Tolerancia a fallos**: si una base falla, la anota en `municipios_con_error` y sigue;
     si fallan todas, lanza un error que se traduce en `502`.
3. **El endpoint**: en `app/api/comentarios.py` (o un archivo nuevo en `app/api/`) agrega la
   ruta, con su router protegido por token.
4. **Registrar** el router en `app/main.py` si creaste uno nuevo.
5. **Probar**: agrega pruebas en `tests/` y corre `poetry run pytest`.

> Para conectarte a las bases **reales** necesitas el túnel/VPC al Cloud SQL y las
> credenciales (pregúntale a DevOps). Para desarrollar, el modo falso es suficiente.

---

## 6. Checklist para tu Pull Request

- [ ] Endpoint en `api/` (con token y descripción clara).
- [ ] Caso A: datos de ejemplo en `datagov_client.py`. · Caso B: repo en `services/` (Falso + Postgres).
- [ ] Variable(s) nueva(s) en `config.py`, `.env` y `.env.example` (si aplica).
- [ ] Router nuevo registrado en `main.py` (solo si creaste uno).
- [ ] Prueba en `tests/` y `poetry run pytest` en verde.
- [ ] Probado en Swagger con modo falso.
- [ ] Si tocaste variables de entorno, avisaste para que se ajuste el despliegue.
