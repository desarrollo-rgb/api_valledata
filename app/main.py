"""Punto de entrada de la API ValleData."""

from fastapi import FastAPI

from app.api import comentarios, datasets

app = FastAPI(
    title="API ValleData",
    version="0.1.0",
)

# Endpoint que republica los datos de DataGov para CKAN (Flujo 1).
app.include_router(datasets.router)
# Endpoint que expone los comentarios de los portales, para DataGov (Flujo 2).
app.include_router(comentarios.router)


@app.get("/")
async def hola_mundo() -> dict[str, str]:
    return {"mensaje": "Hola mundo"}
