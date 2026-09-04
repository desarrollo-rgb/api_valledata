# API ValleData

API en **FastAPI** que actúa como **capa de integración del proyecto ValleData** frente a
DataGov. Tiene dos responsabilidades:

1. **Leer los comentarios** ciudadanos de los **14 portales CKAN** (una base PostgreSQL por
   municipio) y exponerlos en un endpoint propio.
2. **Consumir los datos de cultivos** que expone DataGov (desde BigQuery) y **reexponerlos**
   para que los portales CKAN los puedan ingerir.

> Para entender **por qué** existe este servicio y cómo encaja en el ecosistema, revisa la
> documentación del proyecto. Este README es para **instalar, configurar, correr y contribuir**.

---

## ¿Qué expone? (endpoints)

| Método y ruta | Qué devuelve | Token |
| --- | --- | --- |
| `GET /health` | Liveness: `{"status": "alive"}`. Para la plataforma. | No |
| `GET /ready` | Readiness: revisa que PostgreSQL responda. `200` o `503`. | No |
| `GET /api/v1/dataset_valledata/gold_cultivos_valle_geo` | Cultivos que ValleData obtuvo de DataGov (Flujo 1). Parámetro `limite` (1–1000). | **Sí** |
| `GET /api/v1/bd_ckan/comments` | Comentarios de los 14 portales CKAN, con `municipios_con_error` (Flujo 2). | **Sí** |

**Documentación interactiva** (Swagger) cuando el servidor está arriba: http://localhost:8001/docs

> Convención: ValleData se levanta en el puerto **8001** y DataGov en el **8000**, para que
> puedan correr a la vez en local.

---

## Los dos modos: falso y real

Cada dependencia externa (DataGov y PostgreSQL) tiene **dos implementaciones** detrás de la
misma interfaz, y se elige por configuración:

- **Modo falso** (`true`): responde con datos de ejemplo en memoria. **No llama a DataGov ni
  toca PostgreSQL.** Ideal para desarrollar y correr las pruebas sin credenciales ni red.
- **Modo real** (`false`): llama a DataGov / se conecta a las 14 bases PostgreSQL.

Se controla con `USAR_DATAGOV_FALSO` (Flujo 1) y `USAR_POSTGRES_FALSO` (Flujo 2). Pasar de
falso a real **no cambia ni una línea de código**, solo el `.env`.

---

## 1. Requisitos (se instalan una sola vez en tu máquina)

| Herramienta | Para qué sirve |
| --- | --- |
| **pyenv** | Instala y fija la versión de Python que usa el proyecto (3.11.9) |
| **Poetry** | Gestiona las dependencias y el entorno virtual |
| **gcloud CLI + kubectl** | *Solo para modo real:* túnel al PostgreSQL privado (ver §4.2) |

> Instrucciones para **Windows** (PowerShell). **Tras instalar cada herramienta, cierra y
> vuelve a abrir la terminal** para que el PATH se actualice.

### 1.1 Instalar pyenv (pyenv-win)

1. Abre **PowerShell** y ejecuta el instalador oficial:

   ```powershell
   Invoke-WebRequest -UseBasicParsing -Uri "https://raw.githubusercontent.com/pyenv-win/pyenv-win/master/pyenv-win/install-pyenv-win.ps1" -OutFile "./install-pyenv-win.ps1"; &"./install-pyenv-win.ps1"
   ```

2. Cierra y vuelve a abrir PowerShell.
3. Comprueba: `pyenv --version`

   > Si dice que `pyenv` no se reconoce, reinicia el equipo o revisa la
   > [guía de pyenv-win](https://github.com/pyenv-win/pyenv-win#installation).

### 1.2 Instalar Python con pyenv

```powershell
pyenv install 3.11.9
```
```powershell
pyenv global 3.11.9
```
```powershell
python --version
```

Debe imprimir `Python 3.11.9`.

### 1.3 Instalar Poetry

1. Instala Poetry con su instalador oficial:

   ```powershell
   (Invoke-WebRequest -Uri https://install.python-poetry.org -UseBasicParsing).Content | python -
   ```

2. Agrega al PATH la ruta que te indica el instalador (en Windows suele ser
   `%APPDATA%\Python\Scripts`) y vuelve a abrir la terminal.
3. Comprueba: `poetry --version`

> Este repo ya trae `poetry.toml` para crear el entorno virtual dentro del proyecto (`.venv/`).

> **Mac / Linux:** pyenv con su [guía oficial](https://github.com/pyenv/pyenv#installation)
> (o `brew install pyenv`) y Poetry con `curl -sSL https://install.python-poetry.org | python3 -`.

---

## 2. Puesta en marcha (clonar y correr en modo falso)

Con esto tienes la API corriendo **sin credenciales ni túnel** en ~5 minutos.

**1. Clona el repositorio y entra en la carpeta:**

```bash
git clone https://github.com/desarrollo-rgb/api_valledata.git
```
```bash
cd api_valledata
```

**2. Instala la versión de Python que el proyecto exige** (`.python-version` ya fija `3.11.9`):

```bash
pyenv install 3.11.9
```

**3. Crea tu archivo de configuración local** a partir de la plantilla:

```bash
cp .env.example .env
```

**4. Pon un token cualquiera en el `.env`.** `API_TOKEN` es **obligatorio**: si falta, la
app no arranca. Para desarrollo sirve cualquier valor, por ejemplo:

```
API_TOKEN=dev-local-token-de-prueba
```

> El `.env` es tuyo y **no se sube a git**. En modo falso no necesitas nada más.

**5. Instala las dependencias:**

```bash
poetry install
```

**6. Verifica que todo funciona corriendo las pruebas:**

```bash
poetry run pytest
```

Si ves `15 passed`, todo quedó bien. (Las pruebas corren siempre en modo falso, sin tocar
DataGov ni PostgreSQL, gracias a `tests/conftest.py`.)

**7. Levanta el servidor** (puerto 8001):

```bash
poetry run uvicorn app.main:app --reload --port 8001
```

- Documentación interactiva: http://localhost:8001/docs
- Health check: http://localhost:8001/health

---

## 3. Configuración: el archivo `.env`

### Seguridad

| Variable | Qué es | Valor en desarrollo |
| --- | --- | --- |
| `API_TOKEN` | Token que exige ESTA API. **Obligatorio** (si falta, no arranca). | Un valor de prueba |

### Flujo 1 — cliente hacia DataGov (cultivos)

| Variable | Qué es | Desarrollo (falso) |
| --- | --- | --- |
| `USAR_DATAGOV_FALSO` | `true` = datos de ejemplo; `false` = llama a DataGov | `true` |
| `DATAGOV_API_BASE_URL` | URL base de la API DataGov | `http://localhost:8000` |
| `DATAGOV_API_TOKEN` | Token que DataGov exige. **Debe ser idéntico al `API_TOKEN` de DataGov.** | — |
| `DATAGOV_TIMEOUT_SEGUNDOS` | Timeout de las llamadas | `30` |

### Flujo 2 — PostgreSQL (comentarios CKAN)

| Variable | Qué es | Desarrollo (falso) |
| --- | --- | --- |
| `USAR_POSTGRES_FALSO` | `true` = comentarios de ejemplo; `false` = se conecta a las 14 bases | `true` |
| `POSTGRES_HOST` | Host de PostgreSQL (en local, vía túnel: `127.0.0.1`) | `localhost` |
| `POSTGRES_PORT` | Puerto | `5432` |
| `POSTGRES_USER` | Usuario de BD (idealmente de **solo lectura**) | — |
| `POSTGRES_PASSWORD` | Contraseña del usuario | — |

> Las 14 bases (`ckan_alcala`, `ckan_argelia`, …) están definidas en `app/config.py`
> (`postgres_databases`). Son 14 bases dentro de **una misma instancia**: el código se
> conecta a la misma dirección cambiando el `dbname` en cada vuelta.

---

## 4. Pasar a datos reales

### 4.1 DataGov (Flujo 1)

1. Ten la API DataGov corriendo (por defecto en `http://localhost:8000`).
2. En tu `.env`:
   ```
   USAR_DATAGOV_FALSO=false
   DATAGOV_API_BASE_URL=http://localhost:8000
   DATAGOV_API_TOKEN=<el mismo API_TOKEN configurado en DataGov>
   ```
   > 🔑 Si `DATAGOV_API_TOKEN` no coincide con el `API_TOKEN` de DataGov, recibirás `401`
   > y este endpoint responderá `502`.

### 4.2 PostgreSQL (Flujo 2) — conectarse a las bases privadas

Las bases viven en un **Cloud SQL con solo IP privada** (no tiene IP pública). Tu máquina
local está fuera de la red de GCP, así que **no puede conectarse directo**. La forma que usa
el equipo es un **túnel a través del clúster de Kubernetes** (que sí está dentro de la red).

**Requisitos previos** (una sola vez):

```bash
gcloud components install kubectl
```
```bash
gcloud components install gke-gcloud-auth-plugin
```

> Si da error de permisos, corre esos comandos en una PowerShell **como administrador**.

**Datos que te da el DevOps** (los de abajo son los de QA; confírmalos):

| Dato | Valor QA |
| --- | --- |
| Clúster GKE | `gke-primary` (región `us-east1`, proyecto `co-valledata-prd`) |
| IP privada del Cloud SQL | `10.146.0.3:5432` |
| Usuario / contraseña de BD | (te los entrega el DevOps) |

**Pasos para abrir el túnel:**

**1. Autentícate con la cuenta correcta y fija el proyecto:**

```bash
gcloud auth login datos@valledelcauca.gov.co
```
```bash
gcloud config set project co-valledata-prd
```

**2. Conecta tu `kubectl` al clúster:**

```bash
gcloud container clusters get-credentials gke-primary --region us-east1 --project co-valledata-prd
```

**3. Crea un pod temporal que reenvía hacia el Cloud SQL** (usa `socat` como relevo):

```bash
kubectl run sql-tunnel --image=alpine/socat --restart=Never --labels=app=sql-tunnel -- tcp-listen:5432,fork,reuseaddr tcp-connect:10.146.0.3:5432
```

**4. Espera a que el pod esté listo:**

```bash
kubectl wait --for=condition=Ready pod/sql-tunnel --timeout=60s
```

**5. Abre el túnel** desde tu `localhost:5432` hasta el pod (deja esta terminal abierta):

```bash
kubectl port-forward pod/sql-tunnel 5432:5432
```

Cuando veas `Forwarding from 127.0.0.1:5432 -> 5432`, el túnel está vivo.

**6. En tu `.env`, apunta a `127.0.0.1` y pon las credenciales reales:**

```
USAR_POSTGRES_FALSO=false
POSTGRES_HOST=127.0.0.1
POSTGRES_PORT=5432
POSTGRES_USER=<usuario-de-bd>
POSTGRES_PASSWORD=<contraseña-de-bd>
```

**7. Levanta el API en otra terminal** y prueba `GET /api/v1/bd_ckan/comments`.

> **Al terminar tu sesión:** cierra el `port-forward` con `Ctrl + C` y borra el pod temporal:
> ```bash
> kubectl delete pod sql-tunnel
> ```

> **Seguridad:** el código **solo lee** (nunca escribe en los portales). Además marca cada
> conexión como `read_only`, así que aunque el usuario tuviera permisos de escritura,
> PostgreSQL rechazaría cualquier intento de modificación.

---

## 5. Autenticación: cómo llamar a la API

Los endpoints de datos exigen un **token** en la cabecera `Authorization: Bearer <token>`
(el valor de tu `API_TOKEN`).

Sin token → **401**:

```bash
curl -i "http://localhost:8001/api/v1/bd_ckan/comments"
```

Con el token → **200 + datos**:

```bash
curl -i -H "Authorization: Bearer TU_TOKEN" "http://localhost:8001/api/v1/bd_ckan/comments"
```

Desde el navegador: entra a http://localhost:8001/docs, pulsa **Authorize** 🔒, pega el
token una vez y prueba los endpoints.

---

## 6. Cómo está organizado el proyecto

```
api_valledata/
├── app/
│   ├── main.py                 # arranque de FastAPI; conecta routers y manejadores de error
│   ├── config.py               # lee el .env → Settings (incluye las 14 bases)
│   ├── security.py             # autenticación por token (el "guardián")
│   ├── errors.py               # excepciones de dominio + respuestas de error limpias
│   ├── models/
│   │   └── schemas.py          # contrato de datos (Comentario)
│   ├── api/
│   │   ├── health.py           # GET /health y GET /ready (públicos)
│   │   ├── datasets.py         # GET .../gold_cultivos_valle_geo (reexpone DataGov)
│   │   └── comentarios.py      # GET .../comments (14 bases PostgreSQL)
│   └── services/
│       ├── datagov_client.py   # cómo se piden los cultivos: falso ↔ HTTP a DataGov
│       └── comentarios_repo.py # de dónde salen los comentarios: falso ↔ PostgreSQL
├── tests/                      # pruebas (conftest.py fuerza modo falso)
├── .env.example                # plantilla de configuración (SÍ se versiona)
├── .env                        # tu configuración local (NO se versiona)
├── .python-version             # versión de Python fijada (3.11.9)
├── pyproject.toml / poetry.lock
└── .gitignore
```

**La idea clave del diseño:** los endpoints (`api/`) no saben de dónde vienen los datos.
Eso lo deciden los `services/` según la configuración. Por eso pasar de datos inventados a
reales es solo cambiar el `.env`.

**Detalles de la realidad de CKAN que maneja el código:**

- La columna del texto (`comment`) es un JSON multilingüe `{"es": "...", "en": "..."}` que
  se parsea a `texto_es` / `texto_en` (con tolerancia a texto plano en filas antiguas).
- El `usuario` puede ser **nulo** (comentarios anónimos).
- El `id` **no es único entre municipios**: la clave real es `municipio + id`.
- **Tolerancia a fallos parciales:** si una base no responde, se registra en
  `municipios_con_error` y las demás siguen. Nunca se detiene todo por un municipio.

---

## 7. Manejo de errores

- Si **DataGov está caído** o responde con error, el endpoint de cultivos devuelve un
  **502** limpio (`"No se pudo contactar a la API DataGov"`), no un 500 con traza.
- Si **un municipio** de PostgreSQL falla, su nombre aparece en `municipios_con_error` y el
  resto de comentarios se devuelve igual (no se cae todo).
- Cualquier error no previsto devuelve un **500** genérico; el detalle va al log.
- `GET /ready` devuelve **503** si PostgreSQL no responde (en modo real, p. ej. si el túnel
  está apagado).

---

## 8. Cómo contribuir / hacer cambios

1. Crea una rama: `git checkout -b feature/lo-que-vas-a-hacer`
2. Haz tus cambios y **corre las pruebas** antes de subir: `poetry run pytest`
3. Commit, sube la rama y abre un Pull Request.

**Añadir una librería:**

```bash
poetry add nombre-libreria           # dependencia normal
poetry add --group dev nombre        # solo para desarrollo/pruebas
```

**Convenciones del proyecto:**

- Código y comentarios **en español**.
- **Nunca** subas secretos (tokens, contraseñas de BD). Van en el `.env`. Si algo es secreto
  y debe conocerse, documéntalo en `.env.example` con un valor de ejemplo.
- Contra PostgreSQL: **solo lectura**, nunca escritura en los portales.
- Toda funcionalidad nueva debería venir con su prueba en `tests/`.

**Qué NO se sube al repo** (ya cubierto por `.gitignore`):

| No se sube | Por qué |
| --- | --- |
| `.env` | Configuración local y secretos (incluye credenciales de BD) |
| `.venv/` | Se reconstruye con `poetry install` |
| `__pycache__/`, `.pytest_cache/` | Temporales de Python |

---

## 9. Comandos del día a día

| Qué quieres hacer | Comando |
| --- | --- |
| Levantar el servidor | `poetry run uvicorn app.main:app --reload --port 8001` |
| Correr las pruebas | `poetry run pytest` |
| Abrir el túnel a PostgreSQL | `kubectl port-forward pod/sql-tunnel 5432:5432` |
| Borrar el pod del túnel | `kubectl delete pod sql-tunnel` |
| Añadir una librería | `poetry add nombre` |
| Añadir una librería de desarrollo | `poetry add --group dev nombre` |
| Quitar una librería | `poetry remove nombre` |
| Ver las dependencias instaladas | `poetry show` |
