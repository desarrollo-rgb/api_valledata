# API ValleData

Esqueleto de una API en **FastAPI**, con **pyenv** para fijar la versión de Python y
**Poetry** para gestionar dependencias. Por ahora solo expone un endpoint de prueba
en `GET /`.

Este README documenta **cómo se construyó la plantilla desde cero**, para poder
replicarla en otro proyecto.

---

## Requisitos previos

Se instalan una sola vez en la máquina, no por proyecto.

| Herramienta | Para qué sirve | Comprobar |
| --- | --- | --- |
| [pyenv-win](https://github.com/pyenv-win/pyenv-win) | Instalar y cambiar entre versiones de Python | `pyenv --version` |
| [Poetry](https://python-poetry.org/docs/#installation) | Gestionar dependencias y el entorno virtual | `poetry --version` |

Versiones usadas aquí: pyenv 3.1.1, Poetry 2.2.1.

---

## Paso a paso

### 1. Crear la carpeta e inicializar git

```bash
mkdir api_valledata
```

```bash
cd api_valledata
```

```bash
git init
```

### 2. Fijar la versión de Python con pyenv

Primero mira qué versiones tienes instaladas:

```bash
pyenv versions
```

Si no tienes la que quieres, instálala:

```bash
pyenv install 3.11.9
```

Y fíjala **para este proyecto**:

```bash
pyenv local 3.11.9
```

Esto crea un archivo `.python-version` con el valor `3.11.9`. Desde ahora, cualquier
comando `python` ejecutado dentro de esta carpeta usará esa versión. El archivo **sí se
versiona en git**: es lo que garantiza que todo el equipo use el mismo Python.

Comprueba:

```bash
python --version
```

### 3. Configurar Poetry para crear el entorno dentro del proyecto

Por defecto Poetry guarda los entornos virtuales en una carpeta global del sistema.
Es más cómodo tenerlo dentro del proyecto, en `.venv/`:

```bash
poetry config virtualenvs.in-project true --local
```

El `--local` hace que la configuración aplique **solo a este proyecto**, y la guarda en
un archivo `poetry.toml`. Sin `--local` cambiarías la configuración global de tu máquina.

### 4. Crear el `pyproject.toml`

Este archivo es el centro del proyecto: describe el paquete y sus dependencias.
Puedes generarlo de forma interactiva con `poetry init`, o crearlo a mano:

```toml
[project]
name = "api-valledata"
version = "0.1.0"
description = "Capa de integracion entre ValleData y DataGov"
requires-python = ">=3.11,<4.0"
dependencies = [
    "fastapi (>=0.141,<1.0)",
    "uvicorn[standard] (>=0.52,<1.0)",
]

[tool.poetry]
# Es una aplicacion, no una libreria: no se instala a si misma como paquete.
package-mode = false

[tool.poetry.group.dev.dependencies]
pytest = "^9.1"
httpx = "^0.28"

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]
```

Tres detalles que conviene entender:

- **`package-mode = false`** — Esto es una aplicación que se ejecuta, no una librería que
  otros instalan con `pip install`. Con esta línea, Poetry gestiona las dependencias pero
  no intenta empaquetar e instalar tu propio código.
- **`pythonpath = ["."]`** — Consecuencia de lo anterior: como el proyecto no se instala,
  pytest no encontraría el módulo `app`. Esta línea añade la raíz del proyecto al
  `sys.path` de las pruebas. Sin ella obtienes `ModuleNotFoundError: No module named 'app'`.
- **Grupo `dev`** — `pytest` y `httpx` solo hacen falta para desarrollar y probar. Al
  separarlos, un despliegue en producción puede instalar solo lo necesario con
  `poetry install --without dev`.

### 5. Decirle a Poetry qué Python usar

```bash
poetry env use $(pyenv which python)
```

En Windows, si el comando anterior no resuelve, pasa la ruta completa que devuelve
`pyenv which python`:

```bash
poetry env use C:\Users\TU_USUARIO\.pyenv\pyenv-win\versions\3.11.9\python.exe
```

Este paso es importante: sin él, Poetry usaría el Python que encuentre primero en el
`PATH`, que puede no ser el que fijaste con pyenv.

### 6. Instalar las dependencias

```bash
poetry install
```

Esto crea `.venv/`, instala todo y genera **`poetry.lock`**, un archivo que registra la
versión exacta de cada paquete y de cada dependencia de esas dependencias.
`poetry.lock` **se versiona en git**: es lo que hace que la instalación sea idéntica en
tu máquina, en la de tu compañero y en el servidor.

> Para añadir una librería más adelante: `poetry add nombre-libreria`
> Si es solo para desarrollo: `poetry add --group dev nombre-libreria`

### 7. Escribir la aplicación

Crea la carpeta `app/` con dos archivos.

`app/__init__.py` va **vacío**: su sola presencia marca la carpeta como paquete de
Python, y es lo que permite escribir `from app.main import app`.

`app/main.py`:

```python
"""Punto de entrada de la API ValleData."""

from fastapi import FastAPI

app = FastAPI(
    title="API ValleData",
    version="0.1.0",
)


@app.get("/")
async def hola_mundo() -> dict[str, str]:
    return {"mensaje": "Hola mundo"}
```

### 8. Escribir la prueba

`tests/test_main.py`:

```python
from fastapi.testclient import TestClient

from app.main import app

cliente = TestClient(app)


def test_hola_mundo():
    respuesta = cliente.get("/")
    assert respuesta.status_code == 200
    assert respuesta.json() == {"mensaje": "Hola mundo"}
```

`TestClient` levanta la aplicación en memoria y le hace peticiones reales, sin necesidad
de arrancar un servidor. Viene de Starlette y necesita `httpx` instalado, por eso está en
las dependencias de desarrollo.

### 9. Crear el `.gitignore`

Lo mínimo imprescindible:

```
.venv/
__pycache__/
*.py[cod]
.pytest_cache/
.env
```

La regla clave es que **`.venv/` nunca se sube**: se reconstruye con `poetry install`.
Lo que sí se sube es `pyproject.toml` y `poetry.lock`.

### 10. Verificar que todo funciona

```bash
poetry run pytest
```

```bash
poetry run uvicorn app.main:app --reload --port 8000
```

- Endpoint: http://localhost:8000/
- Documentación interactiva: http://localhost:8000/docs

`--reload` reinicia el servidor cada vez que guardas un archivo. Es para desarrollo; en
producción no se usa.

### 11. Primer commit

```bash
git add -A
```

```bash
git commit -m "chore: plantilla base de la API ValleData"
```

---

## Resumen: qué archivo hace qué

| Archivo | Se versiona | Para qué sirve |
| --- | --- | --- |
| `.python-version` | Sí | Fija la versión de Python (pyenv) |
| `pyproject.toml` | Sí | Declara dependencias y configuración de herramientas |
| `poetry.lock` | Sí | Versiones exactas instaladas: instalación reproducible |
| `poetry.toml` | Sí | Config local de Poetry (entorno dentro del proyecto) |
| `.gitignore` | Sí | Qué no debe subirse |
| `app/main.py` | Sí | La aplicación |
| `tests/` | Sí | Las pruebas |
| `.venv/` | **No** | Entorno virtual, se reconstruye con `poetry install` |

---

## Cómo lo levanta alguien que clona el repo

Todo el paso a paso anterior se reduce a esto para quien llega después:

```bash
git clone https://github.com/desarrollo-rgb/api_valledata.git
```

```bash
cd api_valledata
```

```bash
pyenv install 3.11.9
```

```bash
poetry install
```

```bash
poetry run uvicorn app.main:app --reload --port 8000
```

---

## Estructura final

```
api_valledata/
├── app/
│   ├── __init__.py
│   └── main.py          # aplicacion FastAPI
├── tests/
│   └── test_main.py
├── .python-version      # 3.11.9
├── pyproject.toml       # dependencias y configuracion
├── poetry.lock          # versiones exactas
├── poetry.toml          # config local de Poetry
└── .gitignore
```

---

## Comandos del día a día

| Qué quieres hacer | Comando |
| --- | --- |
| Levantar el servidor | `poetry run uvicorn app.main:app --reload` |
| Correr las pruebas | `poetry run pytest` |
| Añadir una librería | `poetry add nombre` |
| Añadir una librería de desarrollo | `poetry add --group dev nombre` |
| Quitar una librería | `poetry remove nombre` |
| Ver las dependencias instaladas | `poetry show` |
| Abrir una consola dentro del entorno | `poetry env activate` |

---

## Documentos de referencia del proyecto

Están en la carpeta [`apis-externas/`](apis-externas):

- [`CONTEXTO-API-VALLEDATA.md`](apis-externas/CONTEXTO-API-VALLEDATA.md) — qué es este servicio y por qué existe.
- [`IMPLEMENTACION-API-VALLEDATA.md`](apis-externas/IMPLEMENTACION-API-VALLEDATA.md) — el plan de construcción por fases.
- [`CONTEXTO-API-DATAGOV.md`](apis-externas/CONTEXTO-API-DATAGOV.md) y [`IMPLEMENTACION-API-DATAGOV.md`](apis-externas/IMPLEMENTACION-API-DATAGOV.md) — el otro lado de la integración.
