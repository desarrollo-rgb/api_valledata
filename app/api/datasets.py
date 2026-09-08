"""Endpoints que republican los datos de DataGov para que CKAN los ingiera (Flujo 1).

ValleData obtiene cada dataset desde DataGov y lo expone aqui, en su propio endpoint. Es
un pass-through (el mismo JSON). Todos van bajo `consume/` porque el dato viene de otra API
(DataGov). El parametro `limite` se reenvia tal cual a DataGov.
"""

from fastapi import APIRouter, Depends, Query

from app.config import get_settings
from app.security import verificar_token
from app.services.datagov_client import ClienteDataGov, get_cliente_datagov

# La dependencia va en el router: protege TODOS los endpoints de datasets de una vez.
router = APIRouter(
    prefix="/api/v1/consume/dataset_valledata",
    tags=["dataset Valledata"],
    dependencies=[Depends(verificar_token)],
)

# Rango del parametro `limite`, leido de la configuracion (variables LIMITE_MINIMO y
# LIMITE_MAXIMO). Se resuelve al arrancar: cambiarlo en el .env solo requiere reiniciar.
_s = get_settings()
_LIMITE = Query(
    default=None,
    ge=_s.limite_minimo_select,
    le=_s.limite_maximo_select,
    description="Maximo de filas a pedir a DataGov. Vacio = todas (o el maximo, segun PERMITIR_FULL_SELECT).",
)


def _resolver_limite(limite: int | None) -> int | None:
    """Aplica la politica de 'full select' cuando no se especifica `limite`.

    - PERMITIR_FULL_SELECT=true  -> None (se piden todas las filas).
    - PERMITIR_FULL_SELECT=false -> se topa en LIMITE_MAXIMO_SELECT.
    """
    s = get_settings()
    if limite is None and not s.permitir_full_select:
        return s.limite_maximo_select
    return limite


@router.get(
    "/gold_cultivos_valle_geo",
    summary="Obtener información de la tabla de cultivos",
)
async def obtener_cultivos(
    limite: int | None = _LIMITE,
    cliente: ClienteDataGov = Depends(get_cliente_datagov),
) -> dict:
    """Devuelve los datos de cultivos que ValleData obtuvo de DataGov."""
    return cliente.obtener_dataset("gold_cultivos_valle_geo", limite=_resolver_limite(limite))


@router.get(
    "/gold_modelo_rendimiento",
    summary="Obtener información de la tabla de rendimiento",
)
async def obtener_rendimiento(
    limite: int | None = _LIMITE,
    cliente: ClienteDataGov = Depends(get_cliente_datagov),
) -> dict:
    """Devuelve los datos del modelo de rendimiento que ValleData obtuvo de DataGov."""
    return cliente.obtener_dataset("gold_modelo_rendimiento", limite=_resolver_limite(limite))


@router.get(
    "/gold_pronostico_produccion",
    summary="Obtener información de la tabla de pronóstico de producción",
)
async def obtener_pronostico(
    limite: int | None = _LIMITE,
    cliente: ClienteDataGov = Depends(get_cliente_datagov),
) -> dict:
    """Devuelve los datos del pronóstico de producción que ValleData obtuvo de DataGov."""
    return cliente.obtener_dataset("gold_pronostico_produccion", limite=_resolver_limite(limite))


@router.get(
    "/gold_comentarios_sentimiento",
    summary="Obtener información de la tabla de sentimiento de comentarios",
)
async def obtener_sentimiento(
    limite: int | None = _LIMITE,
    cliente: ClienteDataGov = Depends(get_cliente_datagov),
) -> dict:
    """Devuelve el análisis de sentimiento de comentarios que ValleData obtuvo de DataGov."""
    return cliente.obtener_dataset("gold_comentarios_sentimiento", limite=_resolver_limite(limite))
