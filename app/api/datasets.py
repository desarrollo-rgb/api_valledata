"""Endpoints que reexponen las vistas de la analitica de comentarios de DataGov.

ValleData obtiene cada vista desde DataGov y la reexpone aqui (pass-through: el mismo JSON).
Las vistas viven en el dataset `gold_valledata` de DataGov, por eso su URL usa ese nombre.
El parametro `limite` se reenvia tal cual a DataGov.
"""

from fastapi import APIRouter, Depends, Query

from app.security import verificar_token
from app.services.datagov_client import ClienteDataGov, get_cliente_datagov

# La dependencia va en el router: protege TODOS los endpoints de una vez.
router = APIRouter(
    prefix="/api/v1/consume/gold_valledata",
    tags=["dataset Valledata"],
    dependencies=[Depends(verificar_token)],
)

# Parametro `limite`: opcional. Vacio = todas las filas; con valor = tope de filas.
_LIMITE = Query(
    default=None,
    ge=1,
    description="Maximo de filas a pedir a DataGov. Vacio = todas.",
)


@router.get(
    "/valledata_api_comentarios_detalle",
    summary="Obtener el detalle de comentarios analizados",
)
async def obtener_comentarios_detalle(
    limite: int | None = _LIMITE,
    cliente: ClienteDataGov = Depends(get_cliente_datagov),
) -> dict:
    """Devuelve el detalle de comentarios analizados (un comentario por fila) que ValleData obtuvo de DataGov."""
    return cliente.obtener_dataset("gold_valledata", "valledata_api_comentarios_detalle", limite=limite)


@router.get(
    "/valledata_api_comentarios_resumen_dataset",
    summary="Obtener el resumen de comentarios por dataset",
)
async def obtener_comentarios_resumen_dataset(
    limite: int | None = _LIMITE,
    cliente: ClienteDataGov = Depends(get_cliente_datagov),
) -> dict:
    """Devuelve el resumen de comentarios por dataset (totales y porcentajes) que ValleData obtuvo de DataGov."""
    return cliente.obtener_dataset("gold_valledata", "valledata_api_comentarios_resumen_dataset", limite=limite)
