# syntax=docker/dockerfile:1

# ---- Stage 1: builder --------------------------------------------------
# Resuelve e instala las dependencias con Poetry en un venv dentro del
# proyecto. Este stage no llega a la imagen final: solo aporta /app/.venv
# y el codigo fuente ya copiado.
FROM python:3.11-slim AS builder

# Version exacta con la que esta generado poetry.lock (ver su cabecera):
# evita que una version distinta de Poetry re-resuelva el lock de otra forma.
RUN pip install --no-cache-dir poetry==2.2.1

WORKDIR /app

# Copiar solo el manifiesto de dependencias primero (maximiza el cache de
# capas de Docker): si el codigo cambia pero no las dependencias, este
# paso no se vuelve a ejecutar.
COPY pyproject.toml poetry.lock ./

RUN poetry config virtualenvs.in-project true \
    && poetry install --only main --no-root --no-interaction --no-ansi

# Recien ahora el codigo de la app (package-mode = false: no se instala a
# si misma, solo necesita estar presente en el filesystem).
COPY app ./app

# ---- Stage 2: runtime ---------------------------------------------------
# Imagen final: sin Poetry, sin cache de pip, sin dependencias de build.
# Portable y configurable solo por variables de entorno (ver ENV.md),
# para poder correr igual en GKE o en Cloud Run.
FROM python:3.11-slim

RUN useradd --create-home --uid 1000 appuser

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/app /app/app

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8001

USER appuser

EXPOSE 8001

# Liveness liviano contra /health (ver app/api/health.py: no toca Postgres,
# asi que un problema de base de datos no dispara reinicios innecesarios).
# Se resuelve con la stdlib para no tener que instalar curl/wget en la imagen.
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request,os; urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"PORT\",\"8001\")}/health', timeout=2)" || exit 1

# sh -c para poder expandir ${PORT:-8001} (honra el PORT que inyecte la
# plataforma -- p. ej. Cloud Run -- y cae al default local si no hay ninguno
# seteado -- p. ej. GKE con el manifiesto sin esa variable) pero con `exec`
# para que uvicorn reemplace al shell y quede como PID 1: sin esto, `sh` no
# reenvia SIGTERM al proceso hijo y el apagado del contenedor (p. ej. un pod
# terminando en Kubernetes) no seria graceful.
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8001}"]
