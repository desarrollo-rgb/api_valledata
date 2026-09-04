"""Endpoint que republica los datos de DataGov para que CKAN los ingiera (Flujo 1).

ValleData obtiene los datos desde DataGov y los expone aqui, en su propio endpoint. Por
ahora es un pass-through (el mismo JSON); mas adelante se agregara el formato CSV y el
Content-Type que CKAN necesita.
"""

from fastapi import APIRouter, Depends, Query

from app.security import verificar_token
from app.services.datagov_client import ClienteDataGov, get_cliente_datagov

# La dependencia va en el router: protege TODOS los endpoints de datasets de una vez.
router = APIRouter(
    prefix="/api/v1/dataset_valledata",
    tags=["dataset Valledata"],
    dependencies=[Depends(verificar_token)],
)


@router.get(
    "/gold_cultivos_valle_geo",
    summary="Obtener información de la tabla de cultivos",
)
async def obtener_agricultura(
    limite: int = Query(default=100, ge=1, le=1000, description="Maximo de filas a pedir a DataGov."),
    cliente: ClienteDataGov = Depends(get_cliente_datagov),
) -> dict:
    """Devuelve los datos de cultivos que ValleData obtuvo de DataGov."""
    return cliente.obtener_agricultura(limite=limite)
