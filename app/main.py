"""Punto de entrada de la API ValleData."""

from fastapi import FastAPI

from app.api import datasets

app = FastAPI(
    title="API ValleData",
    version="0.1.0",
)

# Endpoint que republica los datos de DataGov para CKAN (Flujo 1).
app.include_router(datasets.router)


@app.get("/")
async def hola_mundo() -> dict[str, str]:
    return {"mensaje": "Hola mundo"}
