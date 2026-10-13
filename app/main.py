"""Punto de entrada de la API ValleData."""

from fastapi import FastAPI

from app.api import comentarios, datasets, health
from app.errors import registrar_manejadores_errores

app = FastAPI(
    title="API ValleData",
    version="0.1.0",
)

# Conecta los manejadores de error: ante un fallo, respuestas HTTP limpias y consistentes.
registrar_manejadores_errores(app)

# Endpoints de salud para la plataforma (liveness/readiness). Publicos, sin token.
app.include_router(health.router)
# Vistas de la analitica de comentarios que ValleData consume de DataGov.
app.include_router(datasets.router)
# Endpoint que expone los comentarios de los portales, para DataGov.
app.include_router(comentarios.router)
