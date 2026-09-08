"""Endpoints que republican los datos de DataGov para que CKAN los ingiera (Flujo 1).

ValleData obtiene cada dataset desde DataGov y lo expone aqui, en su propio endpoint. Es
un pass-through (el mismo JSON). Todos van bajo `consume/` porque el dato viene de otra API
(DataGov). El parametro `limite` se reenvia tal cual a DataGov.
"""

from fastapi import APIRouter, Depends, Query

from app.security import verificar_token
from app.services.datagov_client import ClienteDataGov, get_cliente_datagov

# La dependencia va en el router: protege TODOS los endpoints de datasets de una vez.
router = APIRouter(
    prefix="/api/v1/consume/dataset_valledata",
    tags=["dataset Valledata"],
    dependencies=[Depends(verificar_token)],
)

_LIMITE = Query(default=100, ge=1, le=1000, description="Maximo de filas a pedir a DataGov.")


@router.get(
    "/gold_cultivos_valle_geo",
    summary="Obtener información de la tabla de cultivos",
)
async def obtener_cultivos(
    limite: int = _LIMITE,
    cliente: ClienteDataGov = Depends(get_cliente_datagov),
) -> dict:
    """Devuelve los datos de cultivos que ValleData obtuvo de DataGov."""
    return cliente.obtener_dataset("gold_cultivos_valle_geo", limite=limite)


@router.get(
    "/gold_modelo_rendimiento",
    summary="Obtener información de la tabla de rendimiento",
)
async def obtener_rendimiento(
    limite: int = _LIMITE,
    cliente: ClienteDataGov = Depends(get_cliente_datagov),
) -> dict:
    """Devuelve los datos del modelo de rendimiento que ValleData obtuvo de DataGov."""
    return cliente.obtener_dataset("gold_modelo_rendimiento", limite=limite)


@router.get(
    "/gold_pronostico_produccion",
    summary="Obtener información de la tabla de pronóstico de producción",
)
async def obtener_pronostico(
    limite: int = _LIMITE,
    cliente: ClienteDataGov = Depends(get_cliente_datagov),
) -> dict:
    """Devuelve los datos del pronóstico de producción que ValleData obtuvo de DataGov."""
    return cliente.obtener_dataset("gold_pronostico_produccion", limite=limite)


@router.get(
    "/gold_comentarios_sentimiento",
    summary="Obtener información de la tabla de sentimiento de comentarios",
)
async def obtener_sentimiento(
    limite: int = _LIMITE,
    cliente: ClienteDataGov = Depends(get_cliente_datagov),
) -> dict:
    """Devuelve el análisis de sentimiento de comentarios que ValleData obtuvo de DataGov."""
    return cliente.obtener_dataset("gold_comentarios_sentimiento", limite=limite)
